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
from orchestrator.config_loaders import CopyConfig, load_copy_config
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
        self.cope = CopeClient(settings.cope_api_key)
        self._queue: asyncio.Queue[MintCandidate] = asyncio.Queue(maxsize=200)
        self._seen: set[str] = set()
        self._processing: set[str] = set()
        self._min_score = settings.entry_min_score
        self._live_tracks: dict[str, dict] = {}
        self._copy_wallets: list[str] = list(copy_cfg.wallets)
        self._last_copy_refresh = 0.0
        self._wallet_cache: dict | None = None
        self._get_paused = get_paused or (lambda: False)
        self._on_alert = on_alert

    async def enqueue(self, candidate: MintCandidate) -> None:
        if candidate.mint in self._seen or candidate.mint in self._processing:
            return
        self._seen.add(candidate.mint)
        if self._queue.qsize() > 180:
            return
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
        await self.enqueue(candidate)

    async def refresh_copy_wallets(self) -> list[str]:
        wallets = list(self.copy_cfg.wallets)
        if self.cope.enabled:
            traders = await self.cope.top_traders(limit=self.copy_cfg.max_wallets)
            for w in traders:
                if w not in wallets:
                    wallets.append(w)
        self._copy_wallets = wallets[: self.copy_cfg.max_wallets]
        self._last_copy_refresh = time.time()
        return self._copy_wallets

    async def copy_wallet_poller(self, running: Callable[[], bool]) -> None:
        while running():
            if self.copy_cfg.enabled:
                await self.refresh_copy_wallets()
            await asyncio.sleep(300)

    async def cope_poller(self, running: Callable[[], bool]) -> None:
        while running():
            if self.cope.enabled:
                for c in await self.cope.poll_candidates():
                    await self.enqueue(c)
            await asyncio.sleep(self.settings.cope_poll_sec)

    async def pipeline_worker(self, get_mode: Callable[[], DeskMode], running: Callable[[], bool]) -> None:
        while running():
            try:
                candidate = await asyncio.wait_for(self._queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                continue
            self._processing.add(candidate.mint)
            try:
                await self._run_pipeline(candidate, get_mode())
            finally:
                self._processing.discard(candidate.mint)

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
        if self._get_paused():
            return
        mint = candidate.mint
        await self.broadcast(ev.mint_candidate(mint, candidate.source, candidate.symbol))

        t0 = time.perf_counter()
        scout_verdict, scout_detail = scout_evaluate(
            candidate, min_copy_trader_sol=self.copy_cfg.min_trader_sol
        )
        await self._agent_step(
            "scout",
            mint,
            scout_verdict,
            int((time.perf_counter() - t0) * 1000),
            scout_detail,
        )
        if scout_verdict == "SKIP":
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
        scored = score_candidate(candidate, report, weights, min_score=self._min_score)
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
        sol = self.risk.size_entry_sol(
            mode=mode_str,
            cash_sol=cash,
            trader_sol=float(trader_sol) if trader_sol is not None else None,
            copy_ratio=self.copy_cfg.copy_ratio,
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
                    detail={"price_src": price_src, "trader": candidate.meta.get("trader")},
                )
                self.journal.record_equity(self.paper.equity_sol)
                await self.broadcast(ev.trade_fill("buy", mint, sol, "paper"))
                if self._on_alert:
                    await self._on_alert(f"BUY {candidate.symbol} · {sol:.3f} SOL · paper · {candidate.source}")
                await self._agent_step("executor", mint, "FILLED", 120)
                await self.broadcast(ev.status_snapshot({"wallet": await self.wallet_snapshot(mode)}))
            else:
                await self._agent_step("executor", mint, "REJECTED", 50, "risk_cap")
        elif self.live.ready:
            try:
                result = await self.live.buy(mint, sol)
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
                    detail={"signature": sig, "price_src": price_src, **result},
                )
                self._live_tracks[mint] = {
                    "symbol": candidate.symbol,
                    "entry_sol": sol,
                    "entry_ts": datetime.now(timezone.utc),
                    "source": candidate.source,
                    "peak_pnl_pct": 0.0,
                    "entry_price": price or 0.0001,
                    "tp_hit": set(),
                }
                await self.broadcast(ev.trade_fill("buy", mint, sol, "live"))
                if self._on_alert:
                    await self._on_alert(f"BUY {candidate.symbol} · {sol:.3f} SOL · LIVE · {candidate.source}")
                await self._agent_step("executor", mint, "SUBMITTED", 200, sig[:16] if sig else None)
                await self.broadcast(ev.status_snapshot({"wallet": await self.wallet_snapshot(mode)}))
            except Exception as exc:
                await self._agent_step("executor", mint, "ERROR", 50, str(exc)[:120])
        else:
            await self._agent_step("executor", mint, "NOT_CONFIGURED", 30, "SOLANA_PRIVATE_KEY")

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
                result = await self.live.sell(mint, fraction)
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

    def status_extra(self) -> dict:
        return {
            "copy_trading": {
                "enabled": self.copy_cfg.enabled,
                "wallets": len(self._copy_wallets),
                "pumpportal_required": bool(self.settings.pumpportal_api_key),
            },
            "daily_loss_sol": {
                "paper": round(self.risk.daily_realized_loss_sol("paper"), 4),
                "live": round(self.risk.daily_realized_loss_sol("live"), 4),
            },
        }


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
    copy_cfg = load_copy_config(settings.config_dir)
    desk = DeskRuntime(
        settings, paper, live, journal, broadcast, risk, copy_cfg, get_paused, on_alert
    )
    await desk.refresh_copy_wallets()

    async def feed_heartbeat_loop() -> None:
        while running():
            if on_feed_heartbeat:
                on_feed_heartbeat("pumpportal", status="ok", detail="subscribeNewToken")
                on_feed_heartbeat(
                    "cope",
                    status="ok" if settings.cope_api_key else "off",
                    detail="poll" if settings.cope_api_key else None,
                )
                on_feed_heartbeat(
                    "copy_stream",
                    status="ok" if settings.pumpportal_api_key and copy_cfg.enabled else "off",
                )
            await asyncio.sleep(45)

    tasks = [
        asyncio.create_task(
            pumpportal_listener(
                api_key=settings.pumpportal_api_key,
                on_candidate=desk._on_pump,
                running=running,
            )
        ),
        asyncio.create_task(feed_heartbeat_loop()),
        asyncio.create_task(desk.cope_poller(running)),
        asyncio.create_task(desk.copy_wallet_poller(running)),
        asyncio.create_task(desk.pipeline_worker(get_mode, running)),
        asyncio.create_task(desk.monitor_positions(get_mode, running)),
        asyncio.create_task(desk.learner_scheduler(running)),
    ]

    if settings.pumpportal_api_key and copy_cfg.enabled:

        async def _copy_listener() -> None:
            await account_trade_listener(
                api_key=settings.pumpportal_api_key or "",
                wallets_getter=lambda: desk._copy_wallets,
                on_trade=desk._on_copy_trade,
                running=running,
                copy_boost=copy_cfg.copy_boost,
            )

        tasks.append(asyncio.create_task(_copy_listener()))

    if settings.mock_stream:
        from orchestrator.agents.pipeline import mock_stream_loop

        tasks.append(
            asyncio.create_task(
                mock_stream_loop(settings, get_mode, paper, live, broadcast, running)
            )
        )
    return desk, tasks
