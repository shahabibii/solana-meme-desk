"""Onyx WebSocket event schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


AgentName = Literal[
    "scout", "safety", "copy", "research", "scorer", "executor", "learner"
]


class OnyxEvent(BaseModel):
    type: str
    ts: str = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_wire(self) -> dict[str, Any]:
        return {"type": self.type, "ts": self.ts, **self.payload}


def agent_start(agent: AgentName, mint: str | None = None) -> OnyxEvent:
    return OnyxEvent(type="agent.start", payload={"agent": agent, "mint": mint})


def agent_done(
    agent: AgentName, verdict: str, ms: int, mint: str | None = None, detail: str | None = None
) -> OnyxEvent:
    p: dict[str, Any] = {"agent": agent, "verdict": verdict, "ms": ms, "mint": mint}
    if detail:
        p["detail"] = detail
    return OnyxEvent(type="agent.done", payload=p)


def mint_candidate(mint: str, source: str, symbol: str = "???") -> OnyxEvent:
    return OnyxEvent(
        type="mint.candidate",
        payload={"mint": mint, "source": source, "symbol": symbol},
    )


def mint_blocked(mint: str, reasons: list[str]) -> OnyxEvent:
    return OnyxEvent(type="mint.blocked", payload={"mint": mint, "reasons": reasons})


def trade_fill(side: str, mint: str, sol: float, mode: str) -> OnyxEvent:
    return OnyxEvent(
        type="trade.fill",
        payload={"side": side, "mint": mint, "sol": sol, "mode": mode},
    )


def position_update(mint: str, upnl_pct: float) -> OnyxEvent:
    return OnyxEvent(type="position.update", payload={"mint": mint, "upnl_pct": upnl_pct})


def mode_changed(mode: str) -> OnyxEvent:
    return OnyxEvent(type="desk.mode", payload={"mode": mode})


def status_snapshot(data: dict[str, Any]) -> OnyxEvent:
    return OnyxEvent(type="desk.status", payload=data)
