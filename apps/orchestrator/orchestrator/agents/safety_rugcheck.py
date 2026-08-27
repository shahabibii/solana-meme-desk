"""Rugcheck.xyz + solana-rug style heuristics for Safety agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

RUGCHECK_BASE = "https://api.rugcheck.xyz/v1/tokens"

HIGH_RISK_NAMES = frozenset(
    {
        "freeze authority enabled",
        "mint authority enabled",
        "high holder concentration",
        "low liquidity",
        "rugged",
        "honeypot",
        "mutable metadata",
    }
)


@dataclass
class RugReport:
    score_normalised: int | None
    lp_locked_pct: float | None
    risks: list[str]
    passed: bool
    penalty: int
    ms: int = 0


def _risk_text(item: Any) -> str:
    if isinstance(item, str):
        return item.lower()
    if isinstance(item, dict):
        return str(item.get("name") or item.get("description") or item.get("type") or "").lower()
    return ""


def evaluate_rug_report(data: dict[str, Any] | None) -> RugReport:
    if not data:
        return RugReport(None, None, [], True, 0)

    risks_raw = data.get("risks") or []
    risks = [_risk_text(r) for r in risks_raw if _risk_text(r)]
    score = data.get("score_normalised")
    if score is None and data.get("score") is not None:
        score = int(min(100, max(1, int(data["score"]) // 100)))
    score_int = int(score) if score is not None else None
    lp = data.get("lpLockedPct")
    lp_f = float(lp) if lp is not None else None

    penalty = 0
    hard_block = False
    for r in risks:
        if any(k in r for k in HIGH_RISK_NAMES):
            penalty += 25
            if "freeze" in r or "rugged" in r or "honeypot" in r:
                hard_block = True
        elif r:
            penalty += 8

    if score_int is not None and score_int > 55:
        penalty += min(30, score_int - 40)
    if lp_f is not None and lp_f < 50:
        penalty += 10

    passed = not hard_block and penalty < 45
    return RugReport(score_int, lp_f, risks, passed, min(penalty, 50))


async def fetch_rugcheck(mint: str, timeout: float = 10.0) -> RugReport:
    import time

    t0 = time.perf_counter()
    url = f"{RUGCHECK_BASE}/{mint}/report/summary"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            if r.status_code == 404:
                report = RugReport(None, None, ["no_rugcheck_data"], True, 5)
            elif r.status_code >= 400:
                report = RugReport(None, None, [], True, 0)
            else:
                report = evaluate_rug_report(r.json())
    except Exception:
        report = RugReport(None, None, [], True, 0)
    report.ms = int((time.perf_counter() - t0) * 1000)
    return report
