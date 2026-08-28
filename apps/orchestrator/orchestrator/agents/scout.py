"""Scout agent — source priority, dedup quality, min trader size for copy."""

from __future__ import annotations

from orchestrator.models import MintCandidate

SOURCE_PRIORITY = {
    "copy": 100,
    "convergence": 90,
    "yellowstone": 85,
    "fomo": 80,
    "sniper": 70,
    "pump": 60,
}

MIN_COPY_TRADER_SOL = 0.02


def scout_evaluate(
    candidate: MintCandidate,
    *,
    min_copy_trader_sol: float = MIN_COPY_TRADER_SOL,
    fomo_copy_mode: bool = False,
    allowed_sources: frozenset[str] | None = None,
) -> tuple[str, str | None]:
    """
    Returns (verdict, detail).
    PASS — proceed. SKIP — drop before safety (saves RPC).
    """
    if fomo_copy_mode:
        allowed = allowed_sources or frozenset({"copy", "convergence", "fomo"})
        if candidate.source not in allowed:
            return "SKIP", f"fomo_copy_only:{candidate.source}"

    if candidate.source == "copy":
        trader_sol = candidate.meta.get("trader_sol")
        if trader_sol is not None and float(trader_sol) < min_copy_trader_sol:
            return "SKIP", f"trader_sol<{min_copy_trader_sol}"
        if not candidate.meta.get("trader"):
            return "SKIP", "missing_trader"

    priority = SOURCE_PRIORITY.get(candidate.source, 50)
    if priority < 55 and candidate.copy_boost == 0:
        return "PASS", f"low_priority={priority}"

    return "PASS", f"priority={priority}"
