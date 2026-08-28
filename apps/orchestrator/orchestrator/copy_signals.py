"""Copy-trade convergence tracking, dedup, and mirror-sell helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

MintStatus = Literal["processing", "filled", "blocked", "skipped"]


@dataclass
class CopyImprovementsConfig:
    convergence_window_sec: int = 600
    convergence_min_wallets: int = 2
    convergence_boost_per_wallet: int = 12
    convergence_size_step: float = 0.15
    convergence_size_cap: float = 2.0
    mirror_sell_enabled: bool = True
    mirror_sell_fraction: float = 0.5
    mirror_sell_full_wallets: int = 2
    retry_after_block: bool = True


@dataclass
class _TradeStamp:
    trader: str
    ts: float


@dataclass
class CopySignalTracker:
    cfg: CopyImprovementsConfig
    watched_wallets: set[str] = field(default_factory=set)
    _buys: dict[str, list[_TradeStamp]] = field(default_factory=dict)
    _sells: dict[str, list[_TradeStamp]] = field(default_factory=dict)
    _mint_status: dict[str, MintStatus] = field(default_factory=dict)

    def _prune(self, events: list[_TradeStamp]) -> list[_TradeStamp]:
        cutoff = time.time() - self.cfg.convergence_window_sec
        return [e for e in events if e.ts >= cutoff]

    def record_buy(self, mint: str, trader: str) -> tuple[int, bool]:
        """Returns (distinct_buyer_count, is_new_trader)."""
        key = (trader or "").strip()
        if not key:
            key = "unknown"
        bucket = self._prune(self._buys.get(mint, []))
        is_new = not any(e.trader == key for e in bucket)
        if is_new:
            bucket.append(_TradeStamp(key, time.time()))
        self._buys[mint] = bucket
        return len(bucket), is_new

    def record_sell(self, mint: str, trader: str) -> int:
        key = (trader or "").strip() or "unknown"
        bucket = self._prune(self._sells.get(mint, []))
        if not any(e.trader == key for e in bucket):
            bucket.append(_TradeStamp(key, time.time()))
        self._sells[mint] = bucket
        return len(bucket)

    def convergence_boost(self, count: int) -> int:
        if count < self.cfg.convergence_min_wallets:
            return 0
        extra = count - 1
        return extra * self.cfg.convergence_boost_per_wallet

    def size_multiplier(self, count: int) -> float:
        if count < self.cfg.convergence_min_wallets:
            return 1.0
        extra = count - 1
        mult = 1.0 + extra * self.cfg.convergence_size_step
        return min(self.cfg.convergence_size_cap, mult)

    def should_enqueue_buy(self, mint: str, *, is_new_trader: bool) -> bool:
        status = self._mint_status.get(mint)
        if status == "filled":
            return False
        if status == "processing":
            return False
        if not is_new_trader:
            return False
        if status in ("blocked", "skipped") and self.cfg.retry_after_block:
            return True
        if status in ("blocked", "skipped"):
            return False
        return True

    def set_status(self, mint: str, status: MintStatus) -> None:
        self._mint_status[mint] = status

    def mirror_sell_fraction(self, sell_count: int) -> float:
        if not self.cfg.mirror_sell_enabled:
            return 0.0
        if sell_count >= self.cfg.mirror_sell_full_wallets:
            return 1.0
        if sell_count >= 1:
            return self.cfg.mirror_sell_fraction
        return 0.0
