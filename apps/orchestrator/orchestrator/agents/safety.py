"""Safety agent — mint authority + honeypot checks (Pump.fun-aware)."""

from __future__ import annotations

import time

import httpx

from orchestrator.config import Settings
from orchestrator.models import SafetyReport

SOL_MINT = "So11111111111111111111111111111111111111112"
JUPITER_QUOTE = "https://quote-api.jup.ag/v6/quote"

# Bonding-curve launches — mint authority + no Jupiter route is normal at create time.
PUMP_SOURCES = frozenset({"pump", "sniper", "yellowstone", "fomo", "convergence"})


async def _rpc_get_mint_info(rpc: str, mint: str) -> dict | None:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [mint, {"encoding": "jsonParsed"}],
    }
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.post(rpc, json=payload)
            r.raise_for_status()
            value = (r.json().get("result") or {}).get("value")
            if not value:
                return None
            parsed = (value.get("data") or {}).get("parsed", {})
            return parsed.get("info") if isinstance(parsed, dict) else None
    except Exception:
        return None


async def _jupiter_can_sell(mint: str, amount: int = 1_000_000) -> bool:
    """Tiny quote mint → SOL; no route ≈ honeypot (post-graduation tokens)."""
    params = {
        "inputMint": mint,
        "outputMint": SOL_MINT,
        "amount": str(amount),
        "slippageBps": "5000",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(JUPITER_QUOTE, params=params)
            if r.status_code == 400:
                return False
            r.raise_for_status()
            data = r.json()
            return bool(data.get("outAmount"))
    except Exception:
        return False


def evaluate_safety(
    *,
    mint: str,
    info: dict | None,
    can_sell: bool,
    source: str,
    min_score: int,
) -> SafetyReport:
    """Pure evaluation — Pump.fun path relaxes mint-auth and Jupiter checks."""
    reasons: list[str] = []
    checks: dict[str, bool] = {}
    score = 100
    pump_path = source in PUMP_SOURCES

    if info is None:
        checks["mint_account"] = False
        reasons.append("mint_account_missing")
        score -= 40
    else:
        checks["mint_account"] = True
        mint_auth = info.get("mintAuthority")
        freeze_auth = info.get("freezeAuthority")
        if mint_auth is not None:
            checks["mint_authority_revoked"] = False
            reasons.append("mint_authority_active")
            score -= 5 if pump_path else 35
        else:
            checks["mint_authority_revoked"] = True
        if freeze_auth is not None:
            checks["freeze_authority_revoked"] = False
            reasons.append("freeze_authority_active")
            score -= 25
        else:
            checks["freeze_authority_revoked"] = True

    checks["jupiter_sell_route"] = can_sell
    if not can_sell:
        if pump_path:
            reasons.append("no_jupiter_yet")
            score -= 8
        else:
            reasons.append("honeypot_no_sell_route")
            score -= 50

    score = max(0, min(100, score))

    if pump_path:
        passed = (
            score >= min_score
            and checks.get("mint_account", False)
            and "freeze_authority_active" not in reasons
        )
    else:
        passed = (
            score >= min_score
            and can_sell
            and "mint_authority_active" not in reasons
        )

    return SafetyReport(mint=mint, score=score, passed=passed, reasons=reasons, checks=checks, ms=0)


async def run_safety(mint: str, settings: Settings, *, source: str = "pump") -> SafetyReport:
    t0 = time.perf_counter()
    info = await _rpc_get_mint_info(settings.effective_rpc_url, mint)
    can_sell = await _jupiter_can_sell(mint)
    report = evaluate_safety(
        mint=mint,
        info=info,
        can_sell=can_sell,
        source=source,
        min_score=settings.safety_min_score,
    )
    report.ms = int((time.perf_counter() - t0) * 1000)
    return report
