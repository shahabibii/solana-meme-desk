"""PumpPortal subscribeAccountTrade — mirror fomo / top-wallet buys."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable

import websockets

from orchestrator.models import MintCandidate

OnCopyTrade = Callable[[MintCandidate], Awaitable[None]]

WS_BASE = "wss://pumpportal.fun/api/data"


def _ws_url(api_key: str) -> str:
    return f"{WS_BASE}?api-key={api_key}"


def parse_account_trade(raw: dict[str, Any], *, copy_boost: int = 25) -> MintCandidate | None:
    tx = str(raw.get("txType") or raw.get("action") or "").lower()
    if tx and tx != "buy":
        return None

    mint = raw.get("mint") or raw.get("token") or raw.get("tokenAddress")
    if not mint or len(str(mint)) < 32:
        return None

    trader = str(
        raw.get("traderPublicKey")
        or raw.get("trader")
        or raw.get("user")
        or raw.get("account")
        or ""
    )
    sol = raw.get("solAmount") or raw.get("sol_amount") or raw.get("amount")
    symbol = str(raw.get("symbol") or raw.get("ticker") or "COPY")[:16]

    return MintCandidate(
        mint=str(mint),
        symbol=symbol,
        name=symbol,
        source="copy",
        copy_boost=copy_boost,
        meta={
            "trader": trader,
            "trader_sol": float(sol) if sol is not None else None,
            "trade_event": {k: raw[k] for k in list(raw.keys())[:16]},
        },
    )


async def account_trade_listener(
    *,
    api_key: str,
    wallets_getter: Callable[[], list[str]],
    on_trade: OnCopyTrade,
    running: Callable[[], bool],
    copy_boost: int = 25,
    reconnect_sec: float = 8.0,
) -> None:
    if not api_key:
        while running():
            await asyncio.sleep(30)
        return

    while running():
        wallets = [w for w in wallets_getter() if w][:100]
        if not wallets:
            await asyncio.sleep(30)
            continue
        url = _ws_url(api_key)
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(
                    json.dumps({"method": "subscribeAccountTrade", "keys": wallets})
                )
                async for message in ws:
                    if not running():
                        break
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        cand = parse_account_trade(item, copy_boost=copy_boost)
                        if cand:
                            await on_trade(cand)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(reconnect_sec)
