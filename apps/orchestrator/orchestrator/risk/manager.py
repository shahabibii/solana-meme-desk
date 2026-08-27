"""Risk limits — paper/live caps, daily loss, exit rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from orchestrator.execution.paper import RiskLimits
from orchestrator.journal.store import JournalStore


@dataclass
class FullRiskLimits:
    paper: RiskLimits = field(default_factory=RiskLimits)
    live: RiskLimits = field(default_factory=lambda: RiskLimits(max_open_positions=3))
    paper_max_daily_loss_sol: float = 0.15
    live_max_daily_loss_sol: float = 0.10


def load_full_risk_limits(config_dir: Path) -> FullRiskLimits:
    path = config_dir / "risk.yaml"
    if not path.exists():
        return FullRiskLimits()

    raw = yaml.safe_load(path.read_text()) or {}
    exits = raw.get("exits") or {}
    paper = raw.get("paper") or {}
    live = raw.get("live") or {}

    def _limits(section: dict[str, Any], *, default_open: int) -> RiskLimits:
        return RiskLimits(
            max_position_sol=float(section.get("max_position_sol", 0.05)),
            max_open_positions=int(section.get("max_open_positions", default_open)),
            stop_loss_pct=float(exits.get("stop_loss_pct", 15)),
            take_profit_pct=list(exits.get("take_profit_pct") or [50, 100, 200]),
            take_profit_sell_pct=list(exits.get("take_profit_sell_pct") or [40, 30, 30]),
            trailing_activate_pct=float(exits.get("trailing_activate_pct", 30)),
            trailing_distance_pct=float(exits.get("trailing_distance_pct", 12)),
            max_hold_minutes=int(exits.get("max_hold_minutes", 45)),
        )

    return FullRiskLimits(
        paper=_limits(paper, default_open=5),
        live=_limits(live, default_open=3),
        paper_max_daily_loss_sol=float(paper.get("max_daily_loss_sol", 0.15)),
        live_max_daily_loss_sol=float(live.get("max_daily_loss_sol", 0.10)),
    )


class RiskManager:
    def __init__(self, limits: FullRiskLimits, journal: JournalStore) -> None:
        self.limits = limits
        self.journal = journal

    def limits_for(self, mode: str) -> RiskLimits:
        return self.limits.live if mode == "live" else self.limits.paper

    def max_daily_loss(self, mode: str) -> float:
        return (
            self.limits.live_max_daily_loss_sol
            if mode == "live"
            else self.limits.paper_max_daily_loss_sol
        )

    def daily_realized_loss_sol(self, mode: str) -> float:
        """Sum of SOL lost on losing sells today (UTC)."""
        today = datetime.now(timezone.utc).date().isoformat()
        loss = 0.0
        for t in self.journal.recent_trades(500):
            if t.get("side") != "sell" or t.get("mode") != mode:
                continue
            ts = str(t.get("ts") or "")
            if not ts.startswith(today):
                continue
            pnl = t.get("pnl_pct")
            sol = float(t.get("sol") or 0)
            if pnl is None or float(pnl) >= 0:
                continue
            loss += sol * abs(float(pnl)) / 100.0
        return loss

    def can_open_position(self, *, mode: str, open_count: int) -> tuple[bool, str | None]:
        lim = self.limits_for(mode)
        if open_count >= lim.max_open_positions:
            return False, "max_open_positions"
        if self.daily_realized_loss_sol(mode) >= self.max_daily_loss(mode):
            return False, "max_daily_loss"
        return True, None

    def size_entry_sol(
        self,
        *,
        mode: str,
        cash_sol: float,
        trader_sol: float | None = None,
        copy_ratio: float = 0.25,
    ) -> float:
        lim = self.limits_for(mode)
        base = min(lim.max_position_sol, cash_sol * 0.1)
        if trader_sol and trader_sol > 0:
            base = min(lim.max_position_sol, max(base, trader_sol * copy_ratio))
        return round(max(0.0, base), 4)
