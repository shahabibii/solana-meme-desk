"""Pump.fun bonding-curve quotes (frontend API + trade event reserves)."""

from __future__ import annotations

from typing import Any

import httpx

PUMP_API = "https://frontend-api.pump.fun/coins"


async def pumpfun_price_usd(mint: str, timeout: float = 8.0) -> float | None:
    """Price in USD from Pump.fun coin metadata."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{PUMP_API}/{mint}")
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json() or {}
            usd = data.get("usd_market_cap")
            supply = data.get("total_supply") or data.get("token_supply")
            if usd and supply:
                return float(usd) / float(supply)
            if data.get("price_usd"):
                return float(data["price_usd"])
            sol = bonding_curve_price_sol(data)
            if sol and data.get("sol_price_usd"):
                return sol * float(data["sol_price_usd"])
            return None
    except Exception:
        return None


def bonding_curve_price_sol(coin: dict[str, Any]) -> float | None:
    """Estimate spot price in SOL from virtual reserves."""
    v_sol = coin.get("virtual_sol_reserves") or coin.get("vSolInBondingCurve")
    v_tok = coin.get("virtual_token_reserves") or coin.get("vTokensInBondingCurve")
    if not v_sol or not v_tok:
        return None
    try:
        sol = float(v_sol) / 1e9 if float(v_sol) > 1e6 else float(v_sol)
        tok = float(v_tok) / 1e6 if float(v_tok) > 1e9 else float(v_tok)
        if tok <= 0:
            return None
        return sol / tok
    except (TypeError, ValueError):
        return None


def price_from_trade_event(raw: dict[str, Any]) -> float | None:
    """Derive USD-ish relative price from PumpPortal trade reserves."""
    v_sol = raw.get("vSolInBondingCurve") or raw.get("virtual_sol_reserves")
    v_tok = raw.get("vTokensInBondingCurve") or raw.get("virtual_token_reserves")
    if v_sol and v_tok:
        try:
            sol = float(v_sol) / 1e9 if float(v_sol) > 1e6 else float(v_sol)
            tok = float(v_tok) / 1e6 if float(v_tok) > 1e9 else float(v_tok)
            if tok > 0:
                return sol / tok
        except (TypeError, ValueError):
            pass
    mcap = raw.get("marketCapSol")
    supply = raw.get("tokenAmount")
    if mcap and supply:
        try:
            return float(mcap) / max(float(supply), 1.0)
        except (TypeError, ValueError):
            pass
    return None
