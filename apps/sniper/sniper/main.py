"""Dedicated PumpPortal sniper — forwards mints to orchestrator ingest."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import httpx
import websockets

WS_BASE = "wss://pumpportal.fun/api/data"
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://127.0.0.1:8787").rstrip("/")
INGEST_SECRET = os.environ.get("SNIPER_INGEST_SECRET", "")
PUMPPORTAL_API_KEY = os.environ.get("PUMPPORTAL_API_KEY") or None
SOURCE_TAG = os.environ.get("SNIPER_SOURCE", "sniper")


def _ws_url() -> str:
    if PUMPPORTAL_API_KEY:
        return f"{WS_BASE}?api-key={PUMPPORTAL_API_KEY}"
    return WS_BASE


def parse_new_token(raw: dict[str, Any]) -> tuple[str, str, str] | None:
    mint = (
        raw.get("mint")
        or raw.get("token")
        or raw.get("tokenAddress")
        or (raw.get("data") or {}).get("mint")
    )
    if not mint or len(str(mint)) < 32:
        return None
    symbol = str(raw.get("symbol") or raw.get("ticker") or raw.get("name") or "NEW")[:16]
    name = str(raw.get("name") or symbol)[:64]
    return str(mint), symbol, name


async def post_candidate(mint: str, symbol: str, name: str) -> None:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if INGEST_SECRET:
        headers["X-Sniper-Secret"] = INGEST_SECRET
    body = {
        "mint": mint,
        "symbol": symbol,
        "name": name,
        "source": SOURCE_TAG,
        "copy_boost": 5,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{ORCHESTRATOR_URL}/api/ingest/candidate", json=body, headers=headers)
        if resp.status_code >= 400:
            print(f"ingest failed {resp.status_code}: {resp.text[:120]}", file=sys.stderr)


async def run() -> None:
    print(f"sniper → {ORCHESTRATOR_URL} (source={SOURCE_TAG})")
    while True:
        try:
            async with websockets.connect(_ws_url(), ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("connected to PumpPortal")
                async for message in ws:
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        parsed = parse_new_token(item)
                        if parsed:
                            mint, symbol, name = parsed
                            await post_candidate(mint, symbol, name)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"reconnect in 3s: {exc}", file=sys.stderr)
            await asyncio.sleep(3)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
