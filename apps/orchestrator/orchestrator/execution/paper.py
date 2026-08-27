"""Paper wallet with mark-to-market and exit rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Position:
    mint: str
    symbol: str
    entry_sol: float
    entry_price_usd: float
    quantity: float
    source: str = "pump"
    safety_score: int = 0
    peak_pnl_pct: float = 0.0
    tp_hit: set[float] = field(default_factory=set)
    entry_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RiskLimits:
    max_position_sol: float = 0.05
    max_open_positions: int = 5
    stop_loss_pct: float = 15.0
    take_profit_pct: list[float] = field(default_factory=lambda: [50.0, 100.0])
    take_profit_sell_pct: list[float] = field(default_factory=lambda: [40.0, 30.0])
    trailing_activate_pct: float = 30.0
    trailing_distance_pct: float = 12.0
    max_hold_minutes: int = 45


@dataclass
class PaperBook:
    starting_sol: float
    cash_sol: float
    limits: RiskLimits
    positions: dict[str, Position] = field(default_factory=dict)
    marks: dict[str, float] = field(default_factory=dict)  # mint -> price usd

    @classmethod
    def new(cls, starting_sol: float, limits: RiskLimits | None = None) -> PaperBook:
        return cls(
            starting_sol=starting_sol,
            cash_sol=starting_sol,
            limits=limits or RiskLimits(),
        )

    def can_open(self) -> bool:
        return len(self.positions) < self.limits.max_open_positions

    def buy(
        self,
        mint: str,
        symbol: str,
        sol: float,
        price_usd: float | None,
        *,
        source: str = "pump",
        safety_score: int = 0,
    ) -> bool:
        if sol > self.cash_sol or sol > self.limits.max_position_sol:
            return False
        if not self.can_open() and mint not in self.positions:
            return False
        self.cash_sol -= sol
        px = price_usd or 0.0001
        if mint in self.positions:
            p = self.positions[mint]
            p.entry_sol += sol
            p.quantity += sol / px
        else:
            self.positions[mint] = Position(
                mint=mint,
                symbol=symbol,
                entry_sol=sol,
                entry_price_usd=px,
                quantity=sol / px,
                source=source,
                safety_score=safety_score,
            )
        if price_usd:
            self.marks[mint] = price_usd
        return True

    def mark_price(self, mint: str, price_usd: float) -> None:
        if price_usd > 0:
            self.marks[mint] = price_usd

    def pnl_pct(self, mint: str) -> float | None:
        p = self.positions.get(mint)
        if not p or p.entry_price_usd <= 0:
            return None
        cur = self.marks.get(mint, p.entry_price_usd)
        return ((cur / p.entry_price_usd) - 1.0) * 100.0

    def position_value_sol(self, mint: str) -> float:
        p = self.positions.get(mint)
        if not p:
            return 0.0
        pct = self.pnl_pct(mint) or 0.0
        return p.entry_sol * (1.0 + pct / 100.0)

    def sell(self, mint: str, fraction: float = 1.0) -> tuple[float, float] | None:
        """Returns (proceeds_sol, pnl_pct)."""
        p = self.positions.get(mint)
        if not p:
            return None
        pct = self.pnl_pct(mint) or 0.0
        notional = p.entry_sol * fraction
        proceeds = notional * (1.0 + pct / 100.0)
        self.cash_sol += proceeds
        if fraction >= 1.0:
            del self.positions[mint]
            self.marks.pop(mint, None)
        else:
            p.entry_sol *= 1.0 - fraction
            p.quantity *= 1.0 - fraction
        return proceeds, pct

    @property
    def equity_sol(self) -> float:
        open_val = sum(self.position_value_sol(m) for m in self.positions)
        return self.cash_sol + open_val

    def to_dict(self) -> dict[str, Any]:
        pos_out = []
        for p in self.positions.values():
            pct = self.pnl_pct(p.mint)
            pos_out.append(
                {
                    "mint": p.mint,
                    "symbol": p.symbol,
                    "entry_sol": round(p.entry_sol, 4),
                    "upnl_pct": round(pct, 2) if pct is not None else None,
                    "source": p.source,
                    "safety_score": p.safety_score,
                }
            )
        return {
            "cash_sol": round(self.cash_sol, 4),
            "equity_sol": round(self.equity_sol, 4),
            "starting_sol": self.starting_sol,
            "open_positions": len(self.positions),
            "positions": pos_out,
        }
