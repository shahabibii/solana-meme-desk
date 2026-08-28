"""fomo.family USDC relay buys — meme token often lands in a follow-up tx."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from orchestrator.feeds.copy_filters import USDC_MINT

log = logging.getLogger(__name__)

# fomo routes USDC from trader → router; token delivery is async / separate tx.
FOMO_USDC_ROUTERS = frozenset(
    {
        "7uTT8Xi5RWXzy7h9XL244GRgEycDYDhLjr3ZyNdXi8pZ",
    }
)

TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SOL_PER_USDC = 1.0 / 150.0  # rough sizing proxy for scout min_trader_sol


async def wallet_mints_with_balance(api_key: str, wallet: str) -> dict[str, float]:
    """Return mint -> uiAmount for non-zero SPL holdings."""
    if not api_key or not wallet:
        return {}
    url = f"https://mainnet.helius-rpc.com/?api-key={api_key}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet,
            {"programId": TOKEN_PROGRAM},
            {"encoding": "jsonParsed"},
        ],
    }
    out: dict[str, float] = {}
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            rows = resp.json().get("result", {}).get("value") or []
            for row in rows:
                info = (row.get("account") or {}).get("data", {}).get("parsed", {}).get("info") or {}
                mint = str(info.get("mint") or "")
                amt = (info.get("tokenAmount") or {}).get("uiAmount")
                if mint and amt and float(amt) > 0:
                    out[mint] = float(amt)
    except Exception as exc:
        log.warning("fomo relay mint scan %s: %s", wallet[:8], exc)
    return out


async def wait_for_new_mints(
    api_key: str,
    wallet: str,
    *,
    known: set[str],
    retries: int = 5,
    delay_sec: float = 4.0,
) -> list[tuple[str, float]]:
    """Poll until a new non-stable mint appears in the wallet."""
    found: list[tuple[str, float]] = []
    for attempt in range(retries):
        if attempt:
            await asyncio.sleep(delay_sec)
        holdings = await wallet_mints_with_balance(api_key, wallet)
        for mint, amt in holdings.items():
            if mint in known or mint == USDC_MINT:
                continue
            found.append((mint, amt))
            known.add(mint)
        if found:
            log.info(
                "fomo relay resolved %s new mint(s) for %s after %s tries",
                len(found),
                wallet[:8],
                attempt + 1,
            )
            return found
    return found


def parse_fomo_usdc_relay(tx: dict[str, Any], watched: set[str]) -> dict[str, Any] | None:
    """Detect fomo USDC payment from a watched wallet (meme mint not in same tx)."""
    if tx.get("transactionError"):
        return None
    for tt in tx.get("tokenTransfers") or []:
        if str(tt.get("mint") or "") != USDC_MINT:
            continue
        from_acct = str(tt.get("fromUserAccount") or "")
        to_acct = str(tt.get("toUserAccount") or "")
        if from_acct not in watched or to_acct not in FOMO_USDC_ROUTERS:
            continue
        try:
            usdc = float(tt.get("tokenAmount") or 0)
        except (TypeError, ValueError):
            usdc = 0.0
        if usdc <= 0:
            continue
        sol_proxy = round(usdc * SOL_PER_USDC, 4)
        return {
            "fomo_relay": True,
            "side": "relay",
            "trader": from_acct,
            "trader_usdc": usdc,
            "trader_sol": sol_proxy if sol_proxy >= 0.001 else None,
            "venue": "FOMO",
            "via": "fomo_relay",
            "signature": str(tx.get("signature") or ""),
        }
    return None
