"""Desk runtime — feeds, agent pipeline, position monitor, copy-trading."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from orchestrator.agents.copy import evaluate_copy
from orchestrator.agents.research import run_research
from orchestrator.agents.safety import run_safety
from orchestrator.agents.scorer import run_learner, score_candidate
from orchestrator.agents.scout import scout_evaluate
from orchestrator.config import DeskMode, Settings
from orchestrator.copy_signals import CopyImprovementsConfig, CopySignalTracker, MintStatus
from orchestrator.config_loaders import (
    CopyConfig,
    DeskFeedConfig,
    FomoFollowsConfig,
    load_copy_config,
    load_desk_feed_config,
    load_fomo_follows_config,
    load_fomo_wallets,
    load_fomo_wallets_by_handle,
)
from orchestrator.execution.live import LiveExecutor
from orchestrator.execution.paper import PaperBook, RiskLimits
from orchestrator.feeds.copy_trades import account_trade_listener
from orchestrator.feeds.cope import CopeClient
from orchestrator.feeds.pricing import mark_price_usd
from orchestrator.feeds.pumpportal import pumpportal_listener
from orchestrator.journal.store import JournalStore
from orchestrator.models import MintCandidate
from orchestrator.risk.manager import RiskManager, load_full_risk_limits
from orchestrator.ws import events as ev

Broadcast = Callable[[ev.OnyxEvent], Awaitable[None]]


def load_risk_limits(config_dir: Path) -> RiskLimits:
    return load_full_risk_limits(config_dir).paper


class DeskRuntime:
    def __init__(
        self,
        settings: Settings,
        paper: PaperBook,
        live: LiveExecutor,
        journal: JournalStore,
        broadcast: Broadcast,
        risk: RiskManager,
        copy_cfg: CopyConfig,
        feed_cfg: DeskFeedConfig,
        fomo_follows: FomoFollowsConfig,
        wallets_by_handle: dict[str, str] | None = None,
        get_paused: Callable[[], bool] | None = None,
        on_alert: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self.settings = settings
        self.paper = paper
        self.live = live
        self.journal = journal
        self.broadcast = broadcast
        self.risk = risk
        self.copy_cfg = copy_cfg
        self.feed_cfg = feed_cfg
        self.fomo_follows = fomo_follows
        self._wallets_by_handle = dict(wallets_by_handle or {})
        self.cope = CopeClient(settings.cope_api_key)
        if fomo_follows.handles:
            self.cope.set_manual_handles(fomo_follows.handles)
            self.cope._handles = list(fomo_follows.handles)
        self._queue: asyncio.Queue[MintCandidate] = asyncio.Queue(maxsize=200)
        self._seen: set[str] = set()
        self._processing: set[str] = set()
        imp = feed_cfg.copy_improvements or CopyImprovementsConfig()
        self._copy_tracker = CopySignalTracker(
            imp, watched_wallets=set(copy_cfg.wallets)
        )
        self._min_score = feed_cfg.entry_min_score_default or settings.entry_min_score
        self._live_tracks: dict[str, dict] = {}
        self._copy_wallets: list[str] = list(copy_cfg.wallets)
        self._last_copy_refresh = 0.0
        self._copy_signals_seen = 0
        self._copy_signals_enqueued = 0
        self._helius_webhook_state: dict | None = None
        self._helius_poller_seen: dict[str, set[str]] = {}
        self._wallet_mint_cache: dict[str, dict[str, float]] = {}
        self._fomo_relay_seen: set[str] = set()
        self._wallet_cache: dict | None = None
        self._get_paused = get_paused or (lambda: False)
        self._on_alert = on_alert

    async def enqueue(self, candidate: MintCandidate) -> None:
        if self.feed_cfg.fomo_copy_mode and candidate.source not in self.feed_cfg.allowed_sources:
            return
        mint = candidate.mint
        if candidate.source == "copy":
            trader = str(candidate.meta.get("trader") or "")
            count, is_new = self._copy_tracker.record_buy(mint, trader)
            candidate.meta["convergence_count"] = count
            candidate.copy_boost += self._copy_tracker.convergence_boost(count)
            if not self._copy_tracker.should_enqueue_buy(mint, is_new_trader=is_new):
                return
        else:
            if mint in self._seen or mint in self._processing:
                return
            self._seen.add(mint)
        if mint in self._processing:
            return
        if self._queue.qsize() > 180:
            return
        if candidate.source == "copy":
            self._copy_signals_enqueued += 1
        await self._queue.put(candidate)

    async def ingest_candidate(
        self,
        *,
        mint: str,
        symbol: str = "SNIP",
        name: str = "",
        source: str = "sniper",
        copy_boost: int = 0,
        meta: dict | None = None,
    ) -> bool:
        if len(mint) < 32:
            return False
        cand = MintCandidate(
            mint=mint,
            symbol=symbol[:16],
            name=(name or symbol)[:64],
            source=source,
            copy_boost=copy_boost,
            meta=meta or {},
        )
        await self.enqueue(cand)
        return True

    async def _on_pump(self, candidate: MintCandidate) -> None:
        await self.enqueue(candidate)

    async def _on_copy_trade(self, candidate: MintCandidate) -> None:
        self._copy_signals_seen += 1
        await self.enqueue(candidate)

    async def on_helius_wallet_trade(self, event: dict, mode: DeskMode) -> None:
        """Handle Helius SWAP events from Jupiter, Raydium, Orca, etc."""
        from orchestrator.feeds.helius_wallets import swap_to_candidate

        if event.get("fomo_relay"):
            sig = str(event.get("signature") or "")
            if sig and sig in self._fomo_relay_seen:
                return
            if sig:
                self._fomo_relay_seen.add(sig)
            asyncio.create_task(self._resolve_fomo_relay(event, mode))
            return
        if event.get("side") == "sell":
            await self.handle_copy_sell(event, mode)
            return
        cand = swap_to_candidate(event, copy_boost=self.copy_cfg.copy_boost)
        if cand:
            await self._on_copy_trade(cand)

    async def _resolve_fomo_relay(self, event: dict, mode: DeskMode) -> None:
        """fomo USDC relay: meme token arrives seconds later in wallet."""
        from orchestrator.feeds.fomo_relay import mints_from_txs_after_relay, wait_for_new_mints
        from orchestrator.feeds.helius_wallets import swap_to_candidate

        trader = str(event.get("trader") or "")
        if not trader or not self.settings.helius_api_key:
            return
        known_balances = dict(self._wallet_mint_cache.get(trader, {}))
        new_mints = await wait_for_new_mints(
            self.settings.helius_api_key,
            trader,
            known_balances=known_balances,
            retries=6,
            delay_sec=3.5,
        )
        if not new_mints:
            relay_ts = int(event.get("relay_ts") or 0)
            new_mints = await mints_from_txs_after_relay(
                self.settings.helius_api_key,
                trader,
                after_ts=relay_ts,
                watched=set(self._copy_wallets),
            )
        cache = self._wallet_mint_cache.setdefault(trader, {})
        for mint, amt in new_mints:
            cache[mint] = amt
            buy_event = {
                "side": "buy",
                "mint": mint,
                "trader": trader,
                "trader_sol": event.get("trader_sol"),
                "trader_usdc": event.get("trader_usdc"),
                "venue": "FOMO",
                "via": "fomo_relay",
                "signature": event.get("signature"),
            }
            cand = swap_to_candidate(buy_event, copy_boost=self.copy_cfg.copy_boost)
            if cand:
                cand.meta["trader_usdc"] = event.get("trader_usdc")
                await self._on_copy_trade(cand)

    async def sync_helius_webhook(self) -> dict:
        from orchestrator.feeds.helius_wallets import sync_wallet_webhook

        if not self.settings.helius_api_key or not self.feed_cfg.helius_wallet_watch:
            return {"ok": False, "reason": "helius_wallet_watch_disabled"}
        secret = self.settings.helius_webhook_secret or self.settings.sniper_ingest_secret
        if not secret:
            return {"ok": False, "reason": "HELIUS_WEBHOOK_SECRET not configured"}
        url = f"{self.settings.orchestrator_public_url.rstrip('/')}/api/helius/webhook"
        auth = f"Bearer {secret}"
        result = await sync_wallet_webhook(
            api_key=self.settings.helius_api_key,
            webhook_url=url,
            addresses=list(self._copy_wallets),
            auth_header=auth,
            data_dir=self.settings.data_dir,
        )
        self._helius_webhook_state = result
        return result

    async def backfill_fomo_relays(self, mode: DeskMode, *, minutes: int = 45) -> int:
        """Resolve recent fomo USDC relays missed before relay parser existed."""
        import time

        import httpx

        from orchestrator.feeds.fomo_relay import parse_fomo_usdc_relay

        if not self.settings.helius_api_key:
            return 0
        watched = set(self._copy_wallets)
        if not watched:
            return 0
        cutoff = time.time() - minutes * 60
        resolved = 0
        url_tpl = (
            "https://api.helius.xyz/v0/addresses/{address}/transactions"
            f"?api-key={self.settings.helius_api_key}&limit=15"
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
            for addr in self._copy_wallets:
                try:
                    resp = await client.get(url_tpl.format(address=addr))
                    if resp.status_code != 200:
                        continue
                    for tx in resp.json():
                        if not isinstance(tx, dict):
                            continue
                        ts = int(tx.get("timestamp") or 0)
                        if ts and ts < cutoff:
                            continue
                        relay = parse_fomo_usdc_relay(tx, watched)
                        if relay:
                            await self.on_helius_wallet_trade(relay, mode)
                            resolved += 1
                except Exception:
                    pass
        return resolved

    async def handle_copy_sell(self, event: dict, mode: DeskMode) -> None:
        """Mirror exit when a watched wallet sells a token we hold."""
        imp = self.feed_cfg.copy_improvements
        if not imp or not imp.mirror_sell_enabled:
            return
        mint = str(event.get("mint") or "")
        if len(mint) < 32:
            return
        trader = str(event.get("trader") or "")
        symbol = str(event.get("symbol") or "COPY")
        sell_count = self._copy_tracker.record_sell(mint, trader)
        fraction = self._copy_tracker.mirror_sell_fraction(sell_count)
        if fraction <= 0:
            return

        if mode == DeskMode.PAPER:
            if mint not in self.paper.positions:
                return
            result = self.paper.sell(mint, fraction)
            if not result:
                return
            proceeds, pnl_pct = result
            self.journal.record_trade(
                mint=mint,
                symbol=symbol,
                side="sell",
                sol=proceeds,
                pnl_pct=pnl_pct,
                mode="paper",
                source="copy",
                detail={
                    "exit": "mirror_sell",
                    "trader": trader,
                    "sell_count": sell_count,
                    "fraction": fraction,
                },
            )
            self.journal.record_equity(self.paper.equity_sol)
            await self.broadcast(ev.trade_fill("sell", mint, round(proceeds, 4), "paper"))
            if self._on_alert:
                await self._on_alert(
                    f"Mirror sell {symbol} · {fraction:.0%} · {sell_count} wallet(s) exiting"
                )
            await self.broadcast(ev.status_snapshot({"wallet": await self.wallet_snapshot(mode)}))
            return

        if mode == DeskMode.LIVE and mint in self._live_tracks:
            track = self._live_tracks.get(mint)
            if not track:
                return
            price, _ = await mark_price_usd(mint)
            entry_px = float(track.get("entry_price") or 0.0001)
            pct = ((price / entry_px) - 1.0) * 100.0 if price and entry_px > 0 else 0.0
            sell_venue = event.get("venue") or track.get("venue")
            try:
                result = await self.live.sell_for_venue(
                    mint, fraction, str(sell_venue) if sell_venue else None
                )
                sig = result.get("signature", "")
                proceeds = float(track["entry_sol"]) * fraction * (1.0 + pct / 100.0)
                self.journal.record_trade(
                    mint=mint,
                    symbol=str(track.get("symbol") or symbol),
                    side="sell",
                    sol=proceeds,
                    pnl_pct=pct,
                    mode="live",
                    source="copy",
                    detail={
                        "exit": "mirror_sell",
                        "trader": trader,
                        "sell_count": sell_count,
                        "fraction": fraction,
                        "signature": sig,
                    },
                )
                await self.broadcast(ev.trade_fill("sell", mint, round(proceeds, 4), "live"))
                if fraction >= 1.0:
                    self._live_tracks.pop(mint, None)
                else:
                    track["entry_sol"] = float(track["entry_sol"]) * (1.0 - fraction)
                if self._on_alert:
                    await self._on_alert(
                        f"Mirror sell {symbol} · {fraction:.0%} · {sell_count} wallet(s) exiting"
                    )
                await self.broadcast(ev.status_snapshot({"wallet": await self.wallet_snapshot(mode)}))
            except Exception:
                pass

    async def refresh_copy_wallets(self) -> list[str]:
        wallets = list(self.copy_cfg.wallets)
        if self.cope.enabled:
            if self.settings.fomo_handle:
                await self.cope.sync_fomo(self.settings.fomo_handle)
            handles = await self.cope.resolve_handles()
            if handles:
                self.cope._handles = handles
            for w in await self.cope.wallets_for_handles(handles or self.cope._handles):
                if w not in wallets:
                    wallets.append(w)
            for w in await self.cope.top_traders(limit=self.copy_cfg.max_wallets):
                if w not in wallets:
                    wallets.append(w)
        self._copy_wallets = wallets[: self.copy_cfg.max_wallets]
        self._copy_tracker.watched_wallets = set(self._copy_wallets)
        self._last_copy_refresh = time.time()
        return self._copy_wallets

    async def bootstrap_fomo_copy(self) -> dict:
        """Sync fomo follows, resolve wallets, seed the pipeline from Cope."""
        handle = self.settings.fomo_handle
        handles = list(self.fomo_follows.handles)
        seeded = 0

        if self.cope.enabled:
            if handle:
                await self.cope.sync_fomo(handle)
            resolved = await self.cope.resolve_handles()
            if resolved:
                handles = resolved
            for c in await self.cope.poll_candidates():
                await self.enqueue(c)
                seeded += 1

        wallets = await self.refresh_copy_wallets()
        manual_ok = len(wallets) > 0
        return {
            "ok": manual_ok or seeded > 0,
            "fomo_handle": handle,
            "handles": len(handles),
            "manual_follows": len(self.fomo_follows.handles),
            "wallets": len(wallets),
            "seeded_candidates": seeded,
            "fomo_copy_mode": self.feed_cfg.fomo_copy_mode,
            "follows": handles,
            "copy_watchlist": self._copy_watchlist(),
            "manual_wallets_active": manual_ok,
        }

    def _copy_watchlist(self) -> list[dict[str, str]]:
        wallet_to_handle = {w: h for h, w in self._wallets_by_handle.items()}
        watchlist: list[dict[str, str]] = []
        for w in self._copy_wallets:
            handle = wallet_to_handle.get(w) or "?"
            watchlist.append(
                {
                    "handle": handle,
                    "wallet": w,
                    "wallet_short": f"{w[:4]}…{w[-4:]}",
                }
            )
        return watchlist

    def status_extra(self) -> dict:
        watchlist = self._copy_watchlist()
        base = {
            "fomo_copy_mode": self.feed_cfg.fomo_copy_mode,
            "pump_launch_feed": self.feed_cfg.pump_launch_feed,
            "allowed_sources": sorted(self.feed_cfg.allowed_sources),
            "copy_trading": {
                "enabled": self.copy_cfg.enabled,
                "wallets": len(self._copy_wallets),
                "pumpportal_required": bool(self.settings.pumpportal_api_key),
                "fomo_handle": self.settings.fomo_handle,
                "fomo_handles": list(self.cope._handles or self.fomo_follows.handles)[:20],
                "manual_follows": len(self.fomo_follows.handles),
                "configured_wallets": len(self.copy_cfg.wallets),
                "copy_watchlist": watchlist,
                "manual_wallets_active": len(self._copy_wallets) > 0,
                "copy_signals_seen": self._copy_signals_seen,
                "copy_signals_enqueued": self._copy_signals_enqueued,
                "helius_wallet_watch": self.feed_cfg.helius_wallet_watch,
                "venues": ["pumpportal", "jupiter"],
                "helius_webhook": getattr(self, "_helius_webhook_state", None),
                "mirror_sell": bool(
                    self.feed_cfg.copy_improvements and self.feed_cfg.copy_improvements.mirror_sell_enabled
                ),
                "convergence_window_sec": (
                    self.feed_cfg.copy_improvements.convergence_window_sec
                    if self.feed_cfg.copy_improvements
                    else 600
                ),
            },
            "daily_loss_sol": {
                "paper": round(self.risk.daily_realized_loss_sol("paper"), 4),
                "live": round(self.risk.daily_realized_loss_sol("live"), 4),
            },
        }
        return base

    async def copy_wallet_poller(self, running: Callable[[], bool]) -> None:
        interval = 120 if self.feed_cfg.fomo_copy_mode else 300
        while running():
            if self.copy_cfg.enabled:
                await self.refresh_copy_wallets()
                if self.feed_cfg.helius_wallet_watch and self.settings.helius_api_key:
                    try:
                        await self.sync_helius_webhook()
                    except Exception:
                        pass
            await asyncio.sleep(interval)

    async def cope_poller(self, running: Callable[[], bool]) -> None:
        poll_sec = self.feed_cfg.cope_poll_sec or self.settings.cope_poll_sec
        while running():
            if self.cope.enabled:
                for c in await self.cope.poll_candidates():
                    await self.enqueue(c)
            await asyncio.sleep(poll_sec)

    async def pipeline_worker(self, get_mode: Callable[[], DeskMode], running: Callable[[], bool]) -> None:
        while running():
            try:
                candidate = await asyncio.wait_for(self._queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                continue
            mint = candidate.mint
            self._processing.add(mint)
            if candidate.source == "copy":
                self._copy_tracker.set_status(mint, "processing")
            try:
                await self._run_pipeline(candidate, get_mode())
            finally:
                self._processing.discard(mint)

    async def learner_scheduler(self, running: Callable[[], bool]) -> None:
        while running():
            await asyncio.sleep(3600)
            try:
                run_learner(self.journal)
            except Exception:
                pass

    async def _agent_step(
        self, agent: str, mint: str, verdict: str, ms: int, detail: str | None = None
    ) -> None:
        await self.broadcast(ev.agent_start(agent, mint))  # type: ignore[arg-type]
        await self.broadcast(ev.agent_done(agent, verdict, ms, mint, detail))  # type: ignore[arg-type]

    def _open_count(self, mode: DeskMode) -> int:
        if mode == DeskMode.LIVE:
            return len(self._live_tracks)
        return len(self.paper.positions)

    def _cash_for_sizing(self, mode: DeskMode, on_chain_sol: float | None) -> float:
        if mode == DeskMode.LIVE and on_chain_sol is not None and on_chain_sol > 0:
            return on_chain_sol
        return self.paper.cash_sol

    async def _run_pipeline(self, candidate: MintCandidate, mode: DeskMode) -> None:
        mint = candidate.mint
        outcome: MintStatus = "blocked"
        try:
            if self._get_paused():
                return
            await self.broadcast(ev.mint_candidate(mint, candidate.source, candidate.symbol))

            t0 = time.perf_counter()
            scout_verdict, scout_detail = scout_evaluate(
                candidate,
                min_copy_trader_sol=self.copy_cfg.min_trader_sol,
                fomo_copy_mode=self.feed_cfg.fomo_copy_mode,
                allowed_sources=self.feed_cfg.allowed_sources,
            )
            await self._agent_step(
                "scout",
                mint,
                scout_verdict,
                int((time.perf_counter() - t0) * 1000),
                scout_detail,
            )
            if scout_verdict == "SKIP":
                outcome = "skipped"
                return

            report = await run_safety(mint, self.settings, source=candidate.source)
            await self._agent_step("safety", mint, report.verdict, report.ms, ";".join(report.reasons))
            if not report.passed:
                self.journal.record_block(mint, report.reasons)
                await self.broadcast(ev.mint_blocked(mint, report.reasons))
                return

            copy = evaluate_copy(
                candidate,
                min_trader_sol=self.copy_cfg.min_trader_sol,
                base_boost=self.copy_cfg.copy_boost,
            )
            await self._agent_step("copy", mint, copy.verdict, 45, copy.detail)
            if copy.verdict == "SKIP":
                return
            if copy.boost:
                candidate.copy_boost = max(candidate.copy_boost, copy.boost)

            if self.feed_cfg.fomo_copy_mode and candidate.source == "copy":
                from orchestrator.agents.research import ResearchReport

                research = ResearchReport(thesis="copy mirror", detail="copy_fast_path", ms=0)
            else:
                research = await run_research(
                    candidate,
                    cope_api_key=self.settings.cope_api_key,
                    openai_api_key=self.settings.openai_api_key,
                    llm_enabled=self.settings.research_llm_enabled,
                    safety_score=report.score,
                    openai_model=self.settings.openai_model,
                )
            await self._agent_step("research", mint, research.verdict, research.ms, research.detail)

            weights = self.journal.get_weights()
            scored = score_candidate(
                candidate,
                report,
                weights,
                min_score=self._min_score,
                min_score_by_source=self.feed_cfg.entry_min_score_by_source,
            )
            await self._agent_step(
                "scorer",
                mint,
                "TRADE" if scored.trade else "SKIP",
                25,
                f"score={scored.score}",
            )
            if not scored.trade:
                return

            mode_str = mode.value
            open_n = self._open_count(mode)
            ok, reason = self.risk.can_open_position(mode=mode_str, open_count=open_n)
            if not ok:
                await self._agent_step("executor", mint, "REJECTED", 10, reason)
                if reason == "max_daily_loss" and self._on_alert:
                    await self._on_alert(f"Daily loss cap hit ({mode_str}) — desk blocked new entries.")
                return

            on_chain = await self.live.get_balance_sol() if mode == DeskMode.LIVE else None
            cash = self._cash_for_sizing(mode, on_chain)
            trader_sol = candidate.meta.get("trader_sol")
            conv = int(candidate.meta.get("convergence_count") or 0)
            size_mult = self._copy_tracker.size_multiplier(conv)
            sol = self.risk.size_entry_sol(
                mode=mode_str,
                cash_sol=cash,
                trader_sol=float(trader_sol) if trader_sol is not None else None,
                copy_ratio=self.copy_cfg.copy_ratio,
                size_multiplier=size_mult,
            )
            if sol <= 0.001:
                await self._agent_step("executor", mint, "INSUFFICIENT", 10)
                return

            trade_event = candidate.meta.get("trade_event") if isinstance(candidate.meta.get("trade_event"), dict) else None
            price, price_src = await mark_price_usd(mint, event=trade_event)
            await self.broadcast(ev.agent_start("executor", mint))

            if mode == DeskMode.PAPER:
                ok_buy = self.paper.buy(
                    mint,
                    candidate.symbol,
                    round(sol, 4),
                    price,
                    source=candidate.source,
                    safety_score=report.score,
                )
                if ok_buy:
                    self.journal.record_trade(
                        mint=mint,
                        symbol=candidate.symbol,
                        side="buy",
                        sol=sol,
                        pnl_pct=None,
                        mode="paper",
                        source=candidate.source,
                        safety_score=report.score,
                        detail={
                            "price_src": price_src,
                            "trader": candidate.meta.get("trader"),
                            "convergence_count": conv,
                        },
                    )
                    self.journal.record_equity(self.paper.equity_sol)
                    await self.broadcast(ev.trade_fill("buy", mint, sol, "paper"))
                    if self._on_alert:
                        await self._on_alert(
                            f"BUY {candidate.symbol} · {sol:.3f} SOL · paper · {candidate.source}"
                            + (f" · conv={conv}" if conv >= 2 else "")
                        )
                    await self._agent_step("executor", mint, "FILLED", 120)
                    await self.broadcast(ev.status_snapshot({"wallet": await self.wallet_snapshot(mode)}))
                    outcome = "filled"
                else:
                    await self._agent_step("executor", mint, "REJECTED", 50, "risk_cap")
            elif self.live.ready:
                try:
                    venue = candidate.meta.get("venue")
                    result = await self.live.buy_for_venue(mint, sol, str(venue) if venue else None)
                    sig = result.get("signature", "")
                    self.journal.record_trade(
                        mint=mint,
                        symbol=candidate.symbol,
                        side="buy",
                        sol=sol,
                        pnl_pct=None,
                        mode="live",
                        source=candidate.source,
                        safety_score=report.score,
                        detail={
                            "signature": sig,
                            "price_src": price_src,
                            "convergence_count": conv,
                            "venue": venue,
                            **result,
                        },
                    )
                    self._live_tracks[mint] = {
                        "symbol": candidate.symbol,
                        "entry_sol": sol,
                        "entry_ts": datetime.now(timezone.utc),
                        "source": candidate.source,
                        "venue": venue,
                        "peak_pnl_pct": 0.0,
                        "entry_price": price or 0.0001,
                        "tp_hit": set(),
                    }
                    await self.broadcast(ev.trade_fill("buy", mint, sol, "live"))
                    if self._on_alert:
                        await self._on_alert(
                            f"BUY {candidate.symbol} · {sol:.3f} SOL · LIVE · {candidate.source}"
                            + (f" · conv={conv}" if conv >= 2 else "")
                        )
                    await self._agent_step("executor", mint, "SUBMITTED", 200, sig[:16] if sig else None)
                    await self.broadcast(ev.status_snapshot({"wallet": await self.wallet_snapshot(mode)}))
                    outcome = "filled"
                except Exception as exc:
                    await self._agent_step("executor", mint, "ERROR", 50, str(exc)[:120])
            else:
                await self._agent_step("executor", mint, "NOT_CONFIGURED", 30, "SOLANA_PRIVATE_KEY")
        finally:
            if candidate.source == "copy":
                self._copy_tracker.set_status(mint, outcome)

    async def wallet_snapshot(self, mode: DeskMode) -> dict:
        on_chain = await self.live.get_balance_sol() if self.live.ready else None

        if mode == DeskMode.LIVE and self.live.ready:
            positions = []
            open_mtm = 0.0
            for mint, track in self._live_tracks.items():
                entry_sol = float(track.get("entry_sol", 0))
                entry_px = float(track.get("entry_price") or 0.0001)
                price, _ = await mark_price_usd(mint)
                pct = None
                mtm = entry_sol
                if price and entry_px > 0:
                    pct = ((price / entry_px) - 1.0) * 100.0
                    mtm = entry_sol * (1.0 + pct / 100.0)
                open_mtm += mtm
                positions.append(
                    {
                        "mint": mint,
                        "symbol": track.get("symbol"),
                        "entry_sol": round(entry_sol, 4),
                        "upnl_pct": round(pct, 2) if pct is not None else None,
                        "source": track.get("source"),
                        "safety_score": None,
                    }
                )
            equity = (on_chain or 0.0) + open_mtm
            result = {
                "cash_sol": round(on_chain or 0.0, 4),
                "equity_sol": round(equity, 4),
                "on_chain_sol": round(on_chain, 4) if on_chain is not None else None,
                "starting_sol": None,
                "open_positions": len(self._live_tracks),
                "positions": positions,
                "mode_wallet": "live",
            }
            self._wallet_cache = result
            return result

        snap = self.paper.to_dict()
        snap["mode_wallet"] = "paper"
        snap["on_chain_sol"] = round(on_chain, 4) if on_chain is not None else None
        self._wallet_cache = snap
        return snap

    async def monitor_positions(self, get_mode: Callable[[], DeskMode], running: Callable[[], bool]) -> None:
        while running():
            mode = get_mode()
            if mode == DeskMode.PAPER:
                await self._monitor_paper()
            elif mode == DeskMode.LIVE and self.live.ready:
                await self._monitor_live()
            await asyncio.sleep(10)

    async def _monitor_paper(self) -> None:
        lim = self.risk.limits.paper
        for mint in list(self.paper.positions.keys()):
            p = self.paper.positions.get(mint)
            if not p:
                continue
            price, _ = await mark_price_usd(mint)
            if price:
                self.paper.mark_price(mint, price)
            pct = self.paper.pnl_pct(mint)
            if pct is None:
                continue
            p.peak_pnl_pct = max(p.peak_pnl_pct, pct)
            await self.broadcast(ev.position_update(mint, round(pct, 2)))

            hold_min = (datetime.now(timezone.utc) - p.entry_ts).total_seconds() / 60.0
            exit_reason, fraction, tp_level = self._exit_signal(pct, p.peak_pnl_pct, hold_min, lim, p.tp_hit)

            if exit_reason:
                result = self.paper.sell(mint, fraction)
                if result:
                    if tp_level is not None:
                        p.tp_hit.add(tp_level)
                    proceeds, closed_pct = result
                    self.journal.record_trade(
                        mint=mint,
                        symbol=p.symbol,
                        side="sell",
                        sol=proceeds,
                        pnl_pct=closed_pct,
                        mode="paper",
                        source=p.source,
                        detail={"exit": exit_reason},
                    )
                    self.journal.record_equity(self.paper.equity_sol)
                    await self.broadcast(ev.trade_fill("sell", mint, round(proceeds, 4), "paper"))
                    await self.broadcast(ev.status_snapshot({"wallet": await self.wallet_snapshot(DeskMode.PAPER)}))

    async def _monitor_live(self) -> None:
        lim = self.risk.limits.live
        for mint in list(self._live_tracks.keys()):
            track = self._live_tracks.get(mint)
            if not track:
                continue
            price, _ = await mark_price_usd(mint)
            entry_px = float(track.get("entry_price") or 0.0001)
            if not price or entry_px <= 0:
                continue
            pct = ((price / entry_px) - 1.0) * 100.0
            track["peak_pnl_pct"] = max(float(track.get("peak_pnl_pct", 0)), pct)
            tp_hit: set[float] = track.setdefault("tp_hit", set())
            await self.broadcast(ev.position_update(mint, round(pct, 2)))

            hold_min = (datetime.now(timezone.utc) - track["entry_ts"]).total_seconds() / 60.0
            exit_reason, fraction, tp_level = self._exit_signal(
                pct, float(track["peak_pnl_pct"]), hold_min, lim, tp_hit
            )
            if not exit_reason:
                continue
            try:
                venue = track.get("venue")
                result = await self.live.sell_for_venue(
                    mint, fraction, str(venue) if venue else None
                )
                sig = result.get("signature", "")
                proceeds = float(track["entry_sol"]) * fraction * (1.0 + pct / 100.0)
                if tp_level is not None:
                    tp_hit.add(tp_level)
                self.journal.record_trade(
                    mint=mint,
                    symbol=str(track["symbol"]),
                    side="sell",
                    sol=proceeds,
                    pnl_pct=pct,
                    mode="live",
                    source=str(track.get("source") or "pump"),
                    detail={"exit": exit_reason, "signature": sig},
                )
                await self.broadcast(ev.trade_fill("sell", mint, round(proceeds, 4), "live"))
                if fraction >= 1.0:
                    self._live_tracks.pop(mint, None)
                else:
                    track["entry_sol"] = float(track["entry_sol"]) * (1.0 - fraction)
                await self.broadcast(ev.status_snapshot({"wallet": await self.wallet_snapshot(DeskMode.LIVE)}))
            except Exception:
                pass

    @staticmethod
    def _exit_signal(
        pct: float,
        peak_pnl_pct: float,
        hold_min: float,
        lim: RiskLimits,
        tp_hit: set[float],
    ) -> tuple[str | None, float, float | None]:
        if pct <= -lim.stop_loss_pct:
            return "stop_loss", 1.0, None
        if hold_min >= lim.max_hold_minutes:
            return "max_hold", 1.0, None
        if peak_pnl_pct >= lim.trailing_activate_pct:
            if pct <= peak_pnl_pct - lim.trailing_distance_pct:
                return "trailing_stop", 1.0, None
        for i, tp in enumerate(lim.take_profit_pct):
            if pct >= tp and tp not in tp_hit and i < len(lim.take_profit_sell_pct):
                return f"take_profit_{tp}", lim.take_profit_sell_pct[i] / 100.0, tp
        return None, 1.0, None


async def start_desk(
    settings: Settings,
    get_mode: Callable[[], DeskMode],
    paper: PaperBook,
    live: LiveExecutor,
    journal: JournalStore,
    broadcast: Broadcast,
    running: Callable[[], bool],
    on_feed_heartbeat: Callable[..., None] | None = None,
    get_paused: Callable[[], bool] | None = None,
    on_alert: Callable[[str], Awaitable[None]] | None = None,
) -> tuple[DeskRuntime, list[asyncio.Task]]:
    full = load_full_risk_limits(settings.config_dir)
    paper.limits = full.paper
    risk = RiskManager(full, journal)
    copy_cfg = load_copy_config(settings.config_dir, settings.data_dir)
    feed_cfg = load_desk_feed_config(settings.config_dir)
    fomo_follows = load_fomo_follows_config(settings.config_dir)
    for w in load_fomo_wallets(settings.config_dir):
        if w not in copy_cfg.wallets:
            copy_cfg.wallets.append(w)
    if settings.fomo_copy_mode:
        feed_cfg.fomo_copy_mode = True
        feed_cfg.pump_launch_feed = settings.pump_launch_feed
    if settings.cope_poll_sec != 60:
        feed_cfg.cope_poll_sec = settings.cope_poll_sec
    # Restore persisted fomo handle from volume
    handle_file = settings.data_dir / "fomo_handle.txt"
    if handle_file.exists() and not settings.fomo_handle:
        try:
            settings.fomo_handle = handle_file.read_text().strip() or None
        except Exception:
            pass
    if not settings.fomo_handle and fomo_follows.owner:
        settings.fomo_handle = fomo_follows.owner
    wallets_by_handle = load_fomo_wallets_by_handle(settings.config_dir)
    desk = DeskRuntime(
        settings,
        paper,
        live,
        journal,
        broadcast,
        risk,
        copy_cfg,
        feed_cfg,
        fomo_follows,
        wallets_by_handle,
        get_paused,
        on_alert,
    )
    await desk.refresh_copy_wallets()
    if feed_cfg.helius_wallet_watch and settings.helius_api_key:
        try:
            await desk.sync_helius_webhook()
        except Exception:
            pass
    if feed_cfg.fomo_copy_mode:
        await desk.bootstrap_fomo_copy()

    async def _fomo_relay_backfill() -> None:
        import logging

        from orchestrator.feeds.fomo_relay import wallet_mints_with_balance

        log = logging.getLogger(__name__)
        if settings.helius_api_key:
            for addr in desk._copy_wallets:
                holdings = await wallet_mints_with_balance(settings.helius_api_key, addr)
                desk._wallet_mint_cache[addr] = holdings
        try:
            n = await desk.backfill_fomo_relays(get_mode(), minutes=60)
            if n:
                log.info("fomo relay backfill: %s signals", n)
        except Exception as exc:
            log.warning("fomo relay backfill failed: %s", exc)

    async def feed_heartbeat_loop() -> None:
        while running():
            if on_feed_heartbeat:
                if feed_cfg.pump_launch_feed:
                    on_feed_heartbeat("pumpportal", status="ok", detail="subscribeNewToken")
                else:
                    on_feed_heartbeat("pumpportal", status="off", detail="fomo_copy_mode")
                on_feed_heartbeat(
                    "cope",
                    status="ok" if settings.cope_api_key else "off",
                    detail=f"poll/{feed_cfg.cope_poll_sec}s" if settings.cope_api_key else None,
                )
                on_feed_heartbeat(
                    "copy_stream",
                    status="ok" if settings.pumpportal_api_key and copy_cfg.enabled else "off",
                )
                on_feed_heartbeat(
                    "helius_poller",
                    status="ok" if settings.helius_api_key and feed_cfg.helius_wallet_watch else "off",
                )
                hw = desk._helius_webhook_state or {}
                on_feed_heartbeat(
                    "helius_wallets",
                    status="ok" if hw.get("ok") else "off",
                    detail=f"{hw.get('wallets', 0)} wallets" if hw.get("ok") else hw.get("reason"),
                )
            await asyncio.sleep(45)

    tasks = [
        asyncio.create_task(feed_heartbeat_loop()),
        asyncio.create_task(desk.cope_poller(running)),
        asyncio.create_task(desk.copy_wallet_poller(running)),
        asyncio.create_task(desk.pipeline_worker(get_mode, running)),
        asyncio.create_task(desk.monitor_positions(get_mode, running)),
        asyncio.create_task(desk.learner_scheduler(running)),
    ]

    if feed_cfg.pump_launch_feed:
        tasks.insert(
            0,
            asyncio.create_task(
                pumpportal_listener(
                    api_key=settings.pumpportal_api_key,
                    on_candidate=desk._on_pump,
                    running=running,
                )
            ),
        )

    if settings.pumpportal_api_key and copy_cfg.enabled:

        async def _copy_listener() -> None:
            async def _on_sell(event: dict) -> None:
                await desk.handle_copy_sell(event, get_mode())

            await account_trade_listener(
                api_key=settings.pumpportal_api_key or "",
                wallets_getter=lambda: desk._copy_wallets,
                on_trade=desk._on_copy_trade,
                on_sell=_on_sell,
                running=running,
                copy_boost=copy_cfg.copy_boost,
            )

        tasks.append(asyncio.create_task(_copy_listener()))

    if feed_cfg.helius_wallet_watch and settings.helius_api_key:
        tasks.append(asyncio.create_task(_fomo_relay_backfill()))

    if feed_cfg.helius_wallet_watch and settings.helius_api_key:

        async def _helius_poll_loop() -> None:
            from orchestrator.feeds.helius_poller import poll_wallet_trades

            async def _on_polled(event: dict) -> None:
                await desk.on_helius_wallet_trade(event, get_mode())

            await poll_wallet_trades(
                api_key=settings.helius_api_key or "",
                wallets_getter=lambda: desk._copy_wallets,
                on_trade=_on_polled,
                seen=desk._helius_poller_seen,
                running=running,
                interval_sec=12.0,
                limit=25,
            )

        tasks.append(asyncio.create_task(_helius_poll_loop()))

    if settings.mock_stream:
        from orchestrator.agents.pipeline import mock_stream_loop

        tasks.append(
            asyncio.create_task(
                mock_stream_loop(settings, get_mode, paper, live, broadcast, running)
            )
        )
    return desk, tasks
