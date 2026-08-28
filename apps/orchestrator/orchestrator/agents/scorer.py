"""Scorer — rank candidates; Learner adjusts source weights."""

from __future__ import annotations

from orchestrator.journal.store import JournalStore
from orchestrator.models import MintCandidate, SafetyReport, ScoreResult


def score_candidate(
    candidate: MintCandidate,
    safety: SafetyReport,
    weights: dict[str, float],
    *,
    min_score: int = 72,
    min_score_by_source: dict[str, int] | None = None,
) -> ScoreResult:
    base = safety.score
    w = weights.get(candidate.source, 1.0)
    score = int(min(100, base * w + candidate.copy_boost))
    reasons: list[str] = [f"source={candidate.source}", f"safety={safety.score}"]
    if candidate.copy_boost:
        reasons.append(f"copy_boost=+{candidate.copy_boost}")
    threshold = (min_score_by_source or {}).get(candidate.source, min_score)
    trade = safety.passed and score >= threshold
    if not trade:
        reasons.append(f"below_{threshold}")
    return ScoreResult(mint=candidate.mint, score=score, trade=trade, reasons=reasons)


def run_learner(journal: JournalStore) -> dict[str, float]:
    """Simple EMA-style weight nudge from closed trade sources."""
    trades = journal.recent_trades(200)
    by_source: dict[str, list[float]] = {}
    for t in trades:
        if t.get("side") != "sell" or t.get("pnl_pct") is None:
            continue
        src = str(t.get("source") or "pump")
        by_source.setdefault(src, []).append(float(t["pnl_pct"]))
    weights = journal.get_weights()
    for src, pnls in by_source.items():
        if not pnls:
            continue
        avg = sum(pnls) / len(pnls)
        old = weights.get(src, 1.0)
        # nudge toward profitable sources
        delta = 0.02 if avg > 5 else (-0.02 if avg < -5 else 0)
        new_w = max(0.5, min(1.5, old + delta))
        journal.set_weight(src, new_w)
        weights[src] = new_w
    return weights
