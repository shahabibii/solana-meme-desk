"""PumpPortal WebSocket — new Pump.fun token launches."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable

import websockets

from orchestrator.models import MintCandidate

OnCandidate = Callable[[MintCandidate], Awaitable[None]]

WS_BASE = "wss://pumpportal.fun/api/data"


def _ws_url(api_key: str | None) -> str:
    if api_key:
        return f"{WS_BASE}?api-key={api_key}"
    return WS_BASE


def parse_new_token_message(raw: dict[str, Any]) -> MintCandidate | None:
    """Best-effort parse of PumpPortal new-token payloads."""
    if raw.get("txType") == "create" or raw.get("method") == "subscribeNewToken":
        pass
    mint = (
        raw.get("mint")
        or raw.get("token")
        or raw.get("tokenAddress")
        or (raw.get("data") or {}).get("mint")
    )
    if not mint or len(str(mint)) < 32:
        return None
    symbol = str(
        raw.get("symbol")
        or raw.get("ticker")
        or raw.get("name")
        or "NEW"
    )[:16]
    name = str(raw.get("name") or symbol)[:64]
    return MintCandidate(
        mint=str(mint),
        symbol=symbol,
        name=name,
        source="pump",
        meta={"raw_keys": list(raw.keys())[:12]},
    )


async def pumpportal_listener(
    *,
    api_key: str | None,
    on_candidate: OnCandidate,
    running: Callable[[], bool],
    reconnect_sec: float = 5.0,
) -> None:
    """Subscribe to new token creates; reconnect on drop."""
    while running():
        url = _ws_url(api_key)
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                async for message in ws:
                    if not running():
                        break
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                cand = parse_new_token_message(item)
                                if cand:
                                    await on_candidate(cand)
                        continue
                    if isinstance(data, dict):
                        cand = parse_new_token_message(data)
                        if cand:
                            await on_candidate(cand)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(reconnect_sec)
