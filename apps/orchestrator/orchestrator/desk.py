"""Desk runtime — feeds, agent pipeline, position monitor."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

import yaml

from orchestrator.agents.safety import run_safety
from orchestrator.agents.scorer import score_candidate
from orchestrator.config import DeskMode, Settings
from orchestrator.execution.live import LiveExecutor
from orchestrator.execution.paper import PaperBook, RiskLimits
from orchestrator.feeds.cope import CopeClient
from orchestrator.feeds.dexscreener import token_price_usd
from orchestrator.feeds.pumpportal import pumpportal_listener
from orchestrator.journal.store import JournalStore
from orchestrator.models import MintCandidate
from orchestrator.ws import events as ev

Broadcast = Callable[[ev.OnyxEvent], Awaitable[None]]

AGENTS = ("scout", "safety", "copy", "research", "scorer", "executor")


def load_risk_limits(config_dir: Path) -> RiskLimits:
    path = config_dir / "risk.yaml"
    if not path.exists():
        return RiskLimits()
    raw = yaml.safe_load(path.read_text()) or {}
    exits = raw.get("exits") or {}
    paper = raw.get("paper") or {}
    return RiskLimits(
        max_position_sol=float(paper.get("max_position_sol", 0.05)),
        max_open_positions=int(paper.get("max_open_positions", 5)),
        stop_loss_pct=float(exits.get("stop_loss_pct", 15)),
        take_profit_pct=list(exits.get("take_profit_pct") or [50, 100]),
        take_profit_sell_pct=list(exits.get("take_profit_sell_pct") or [40, 30]),
        trailing_activate_pct=float(exits.get("trailing_activate_pct", 30)),
        trailing_distance_pct=float(exits.get("trailing_distance_pct", 12)),
        max_hold_minutes=int(exits.get("max_hold_minutes", 45)),
    )


class DeskRuntime:
    def __init__(
        self,
        settings: Settings,
        paper: PaperBook,
        live: LiveExecutor,
        journal: JournalStore,
        broadcast: Broadcast,
    ) -> None:
        self.settings = settings
        self.paper = paper
        self.live = live
        self.journal = journal
        self.broadcast = broadcast
        self.cope = CopeClient(settings.cope_api_key)
        self._queue: asyncio.Queue[MintCandidate] = asyncio.Queue(maxsize=200)
        self._seen: set[str] = set()
        self._processing: set[str] = set()
        self._min_score = settings.entry_min_score

    async def enqueue(self, candidate: MintCandidate) -> None:
        if candidate.mint in self._seen or candidate.mint in self._processing:
            return
        self._seen.add(candidate.mint)
        if self._queue.qsize() > 180:
            return
        await self._queue.put(candidate)

    async def _on_pump(self, candidate: MintCandidate) -> None:
        await self.enqueue(candidate)

    async def cope_poller(self, running: Callable[[], bool]) -> None:
        while running():
            if self.cope.enabled:
                for c in await self.cope.poll_candidates():
                    await self.enqueue(c)
            await asyncio.sleep(60)

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

    async def _agent_step(
        self, agent: str, mint: str, verdict: str, ms: int, detail: str | None = None
    ) -> None:
        await self.broadcast(ev.agent_start(agent, mint))  # type: ignore[arg-type]
        await self.broadcast(ev.agent_done(agent, verdict, ms, mint, detail))  # type: ignore[arg-type]

    async def _run_pipeline(self, candidate: MintCandidate, mode: DeskMode) -> None:
        mint = candidate.mint
        await self.broadcast(ev.mint_candidate(mint, candidate.source, candidate.symbol))

        # Scout
        t0 = time.perf_counter()
        await self._agent_step("scout", mint, "PASS", int((time.perf_counter() - t0) * 1000))

        # Safety
        report = await run_safety(mint, self.settings)
        await self._agent_step("safety", mint, report.verdict, report.ms, ";".join(report.reasons))
        if not report.passed:
            self.journal.record_block(mint, report.reasons)
            await self.broadcast(ev.mint_blocked(mint, report.reasons))
            return

        # Copy
        copy_verdict = "BOOST" if candidate.copy_boost else "NEUTRAL"
        await self._agent_step("copy", mint, copy_verdict, 40)

        # Research (thesis stub — fomo meta if present)
        thesis = "pump_launch" if candidate.source == "pump" else candidate.source
        await self._agent_step("research", mint, "PASS", 35, thesis)

        # Scorer
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

        # Executor
        sol = min(self.paper.limits.max_position_sol, self.paper.cash_sol * 0.1)
        if sol <= 0.001:
            await self._agent_step("executor", mint, "INSUFFICIENT", 10)
            return

        price = await token_price_usd(mint)
        await self.broadcast(ev.agent_start("executor", mint))

        if mode == DeskMode.PAPER:
            ok = self.paper.buy(
                mint,
                candidate.symbol,
                round(sol, 4),
                price,
                source=candidate.source,
                safety_score=report.score,
            )
            if ok:
                self.journal.record_trade(
                    mint=mint,
                    symbol=candidate.symbol,
                    side="buy",
                    sol=sol,
                    pnl_pct=None,
                    mode="paper",
                    source=candidate.source,
                    safety_score=report.score,
                )
                self.journal.record_equity(self.paper.equity_sol)
                await self.broadcast(ev.trade_fill("buy", mint, sol, "paper"))
                await self._agent_step("executor", mint, "FILLED", 120)
                await self.broadcast(ev.status_snapshot({"wallet": self.paper.to_dict()}))
            else:
                await self._agent_step("executor", mint, "REJECTED", 50, "risk_cap")
        else:
            if self.live.ready:
                try:
                    await self.live.buy(mint, sol)
                    await self.broadcast(ev.trade_fill("buy", mint, sol, "live"))
                    await self._agent_step("executor", mint, "SUBMITTED", 200)
                except Exception as exc:
                    await self._agent_step("executor", mint, "ERROR", 50, str(exc))
            else:
                await self._agent_step(
                    "executor", mint, "NOT_CONFIGURED", 30, "SOLANA_PRIVATE_KEY"
                )

    async def monitor_positions(self, running: Callable[[], bool]) -> None:
        """Mark-to-market + TP/SL/trail/max-hold exits."""
        while running():
            for mint in list(self.paper.positions.keys()):
                p = self.paper.positions.get(mint)
                if not p:
                    continue
                price = await token_price_usd(mint)
                if price:
                    self.paper.mark_price(mint, price)
                pct = self.paper.pnl_pct(mint)
                if pct is None:
                    continue
                p.peak_pnl_pct = max(p.peak_pnl_pct, pct)
                await self.broadcast(ev.position_update(mint, round(pct, 2)))

                lim = self.paper.limits
                hold_min = (datetime.now(timezone.utc) - p.entry_ts).total_seconds() / 60.0
                exit_reason: str | None = None
                fraction = 1.0

                if pct <= -lim.stop_loss_pct:
                    exit_reason = "stop_loss"
                elif hold_min >= lim.max_hold_minutes:
                    exit_reason = "max_hold"
                elif p.peak_pnl_pct >= lim.trailing_activate_pct:
                    if pct <= p.peak_pnl_pct - lim.trailing_distance_pct:
                        exit_reason = "trailing_stop"
                else:
                    for i, tp in enumerate(lim.take_profit_pct):
                        if pct >= tp and i < len(lim.take_profit_sell_pct):
                            exit_reason = f"take_profit_{tp}"
                            fraction = lim.take_profit_sell_pct[i] / 100.0
                            break

                if exit_reason:
                    result = self.paper.sell(mint, fraction)
                    if result:
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
                        await self.broadcast(
                            ev.trade_fill("sell", mint, round(proceeds, 4), "paper")
                        )
                        await self.broadcast(ev.status_snapshot({"wallet": self.paper.to_dict()}))

            await asyncio.sleep(10)


async def start_desk(
    settings: Settings,
    get_mode: Callable[[], DeskMode],
    paper: PaperBook,
    live: LiveExecutor,
    journal: JournalStore,
    broadcast: Broadcast,
    running: Callable[[], bool],
) -> list[asyncio.Task]:
    desk = DeskRuntime(settings, paper, live, journal, broadcast)
    tasks = [
        asyncio.create_task(
            pumpportal_listener(
                api_key=settings.pumpportal_api_key,
                on_candidate=desk._on_pump,
                running=running,
            )
        ),
        asyncio.create_task(desk.cope_poller(running)),
        asyncio.create_task(desk.pipeline_worker(get_mode, running)),
        asyncio.create_task(desk.monitor_positions(running)),
    ]
    if settings.mock_stream:
        from orchestrator.agents.pipeline import mock_stream_loop

        tasks.append(
            asyncio.create_task(
                mock_stream_loop(settings, get_mode, paper, live, broadcast, running)
            )
        )
    return tasks
