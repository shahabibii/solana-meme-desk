"""Unified token pricing — Pump.fun first, DexScreener fallback."""

from __future__ import annotations

from typing import Any

from orchestrator.feeds.dexscreener import token_price_usd as dex_price_usd
from orchestrator.feeds.pumpfun import price_from_trade_event, pumpfun_price_usd


async def mark_price_usd(mint: str, *, event: dict[str, Any] | None = None) -> tuple[float | None, str]:
    if event:
        px = price_from_trade_event(event)
        if px and px > 0:
            return px, "bonding_curve_event"

    px = await pumpfun_price_usd(mint)
    if px and px > 0:
        return px, "pumpfun_api"

    px = await dex_price_usd(mint)
    if px and px > 0:
        return px, "dexscreener"

    return None, "none"
