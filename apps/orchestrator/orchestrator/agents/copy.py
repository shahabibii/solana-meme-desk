"""Copy agent — evaluate smart-money mirror signals."""

from __future__ import annotations

from dataclasses import dataclass

from orchestrator.models import MintCandidate


@dataclass
class CopyVerdict:
    verdict: str
    boost: int
    detail: str

    @property
    def passed(self) -> bool:
        return self.verdict in {"MIRROR", "BOOST"}


def evaluate_copy(
    candidate: MintCandidate,
    *,
    min_trader_sol: float = 0.02,
    base_boost: int = 25,
) -> CopyVerdict:
    if candidate.source != "copy":
        boost = candidate.copy_boost
        if boost > 0:
            return CopyVerdict("BOOST", boost, f"signal_boost=+{boost}")
        return CopyVerdict("NEUTRAL", 0, "no_copy_signal")

    trader = str(candidate.meta.get("trader") or "")[:8]
    trader_sol = candidate.meta.get("trader_sol")
    if trader_sol is not None and float(trader_sol) < min_trader_sol:
        return CopyVerdict("SKIP", 0, f"trader_size={trader_sol}")

    boost = max(base_boost, candidate.copy_boost)
    detail = f"mirror {trader}…"
    if trader_sol:
        detail += f" {float(trader_sol):.3f} SOL"
    return CopyVerdict("MIRROR", boost, detail)
