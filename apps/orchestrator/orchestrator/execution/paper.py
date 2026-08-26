"""Paper wallet and simulated fills."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Position:
    mint: str
    symbol: str
    entry_sol: float
    quantity: float
    entry_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PaperBook:
    starting_sol: float
    cash_sol: float
    positions: dict[str, Position] = field(default_factory=dict)

    @classmethod
    def new(cls, starting_sol: float) -> PaperBook:
        return cls(starting_sol=starting_sol, cash_sol=starting_sol)

    def buy(self, mint: str, symbol: str, sol: float) -> bool:
        if sol > self.cash_sol:
            return False
        self.cash_sol -= sol
        if mint in self.positions:
            p = self.positions[mint]
            p.entry_sol += sol
            p.quantity += sol  # simplified: 1 unit ~ 1 SOL notional
        else:
            self.positions[mint] = Position(mint=mint, symbol=symbol, entry_sol=sol, quantity=sol)
        return True

    def sell(self, mint: str, fraction: float = 1.0) -> float | None:
        p = self.positions.get(mint)
        if not p:
            return None
        proceeds = p.entry_sol * fraction * 1.05  # stub +5% for demo
        self.cash_sol += proceeds
        if fraction >= 1.0:
            del self.positions[mint]
        else:
            p.entry_sol *= 1 - fraction
            p.quantity *= 1 - fraction
        return proceeds

    @property
    def equity_sol(self) -> float:
        open_notional = sum(p.entry_sol for p in self.positions.values())
        return self.cash_sol + open_notional

    def to_dict(self) -> dict:
        return {
            "cash_sol": round(self.cash_sol, 4),
            "equity_sol": round(self.equity_sol, 4),
            "starting_sol": self.starting_sol,
            "open_positions": len(self.positions),
            "positions": [
                {
                    "mint": p.mint,
                    "symbol": p.symbol,
                    "entry_sol": round(p.entry_sol, 4),
                }
                for p in self.positions.values()
            ],
        }
