"""Domain models for the meme desk."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MintCandidate:
    mint: str
    symbol: str
    name: str = ""
    source: str = "pump"  # pump | fomo | convergence
    meta: dict[str, Any] = field(default_factory=dict)
    copy_boost: int = 0
    discovered_at: datetime = field(default_factory=utc_now)


@dataclass
class SafetyReport:
    mint: str
    score: int
    passed: bool
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    ms: int = 0

    @property
    def verdict(self) -> str:
        return "PASS" if self.passed else "BLOCK"


@dataclass
class ScoreResult:
    mint: str
    score: int
    trade: bool
    reasons: list[str] = field(default_factory=list)
