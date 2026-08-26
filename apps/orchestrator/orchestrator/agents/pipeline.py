"""Agent pipeline — mock stream for Onyx demo; real feeds in Phase 2."""

from __future__ import annotations

import asyncio
import random
import string
from typing import Awaitable, Callable

from orchestrator.config import DeskMode, Settings
from orchestrator.execution.live import LiveExecutor
from orchestrator.execution.paper import PaperBook
from orchestrator.ws import events as ev

Broadcast = Callable[[ev.OnyxEvent], Awaitable[None]]

AGENTS = ("scout", "safety", "copy", "research", "scorer", "executor", "learner")


def _fake_mint() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=44))


def _fake_symbol() -> str:
    return random.choice(["PEPE", "BONK2", "WIF", "POPCAT", "MOOD"]) + str(random.randint(1, 99))


async def run_pipeline(
    *,
    settings: Settings,
    mode: DeskMode,
    paper: PaperBook,
    live: LiveExecutor,
    broadcast: Broadcast,
) -> None:
    mint = _fake_mint()
    symbol = _fake_symbol()
    source = random.choice(["pump", "fomo", "convergence"])
    await broadcast(ev.mint_candidate(mint, source, symbol))

    for agent in AGENTS[:-1]:  # learner runs nightly
        await broadcast(ev.agent_start(agent, mint))  # type: ignore[arg-type]
        await asyncio.sleep(random.uniform(0.15, 0.45))
        ms = random.randint(40, 320)

        if agent == "safety" and random.random() < 0.25:
            reasons = random.sample(
                ["honeypot_sim_fail", "mint_authority_active", "dev_concentration_42pct"],
                k=random.randint(1, 2),
            )
            await broadcast(ev.agent_done(agent, "BLOCK", ms, mint, ";".join(reasons)))  # type: ignore[arg-type]
            await broadcast(ev.mint_blocked(mint, reasons))
            return

        verdict = "PASS" if agent != "scorer" else ("TRADE" if random.random() > 0.35 else "SKIP")
        await broadcast(ev.agent_done(agent, verdict, ms, mint))  # type: ignore[arg-type]

    # Executor
    await broadcast(ev.agent_start("executor", mint))
    await asyncio.sleep(0.2)
    sol = round(random.uniform(0.01, 0.05), 3)

    if mode == DeskMode.PAPER:
        if paper.buy(mint, symbol, sol):
            await broadcast(ev.trade_fill("buy", mint, sol, "paper"))
            await broadcast(ev.agent_done("executor", "FILLED", 180, mint))
            await broadcast(ev.status_snapshot({"wallet": paper.to_dict()}))
        else:
            await broadcast(ev.agent_done("executor", "INSUFFICIENT", 50, mint))
    else:
        if live.ready:
            try:
                await live.buy(mint, sol)
                await broadcast(ev.trade_fill("buy", mint, sol, "live"))
                await broadcast(ev.agent_done("executor", "SUBMITTED", 220, mint))
            except RuntimeError as exc:
                await broadcast(ev.agent_done("executor", "ERROR", 50, mint, str(exc)))
        else:
            await broadcast(
                ev.agent_done(
                    "executor",
                    "NOT_CONFIGURED",
                    30,
                    mint,
                    "Set SOLANA_PRIVATE_KEY for live trading",
                )
            )

    if mint in paper.positions:
        await asyncio.sleep(1.0)
        upnl = round(random.uniform(-12, 85), 1)
        await broadcast(ev.position_update(mint, upnl))


async def mock_stream_loop(
    settings: Settings,
    get_mode: Callable[[], DeskMode],
    paper: PaperBook,
    live: LiveExecutor,
    broadcast: Broadcast,
    running: Callable[[], bool],
) -> None:
    while running():
        if settings.mock_stream:
            await run_pipeline(
                settings=settings,
                mode=get_mode(),
                paper=paper,
                live=live,
                broadcast=broadcast,
            )
        await asyncio.sleep(random.uniform(4, 8))
