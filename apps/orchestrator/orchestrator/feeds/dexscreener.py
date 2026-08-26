"""DexScreener price quotes for paper PnL and monitor."""

from __future__ import annotations

import httpx

SOL_MINT = "So11111111111111111111111111111111111111112"


async def token_price_usd(mint: str, timeout: float = 8.0) -> float | None:
    url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            pairs = (r.json() or {}).get("pairs") or []
            if not pairs:
                return None
            # Prefer highest liquidity SOL pair
            best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd") or 0))
            return float(best.get("priceUsd") or 0) or None
    except Exception:
        return None
