"""Safety agent — mint authority + Jupiter sell-route honeypot check."""

from __future__ import annotations

import time

import httpx

from orchestrator.config import Settings
from orchestrator.models import SafetyReport

SOL_MINT = "So11111111111111111111111111111111111111112"
JUPITER_QUOTE = "https://quote-api.jup.ag/v6/quote"


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
    """Tiny quote mint → SOL; no route ≈ honeypot."""
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


async def run_safety(mint: str, settings: Settings) -> SafetyReport:
    t0 = time.perf_counter()
    reasons: list[str] = []
    checks: dict[str, bool] = {}
    score = 100

    info = await _rpc_get_mint_info(settings.solana_rpc_url, mint)
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
            score -= 35
        else:
            checks["mint_authority_revoked"] = True
        if freeze_auth is not None:
            checks["freeze_authority_revoked"] = False
            reasons.append("freeze_authority_active")
            score -= 25
        else:
            checks["freeze_authority_revoked"] = True

    can_sell = await _jupiter_can_sell(mint)
    checks["jupiter_sell_route"] = can_sell
    if not can_sell:
        reasons.append("honeypot_no_sell_route")
        score -= 50

    score = max(0, min(100, score))
    passed = score >= settings.safety_min_score and can_sell and "mint_authority_active" not in reasons

    ms = int((time.perf_counter() - t0) * 1000)
    return SafetyReport(mint=mint, score=score, passed=passed, reasons=reasons, checks=checks, ms=ms)
