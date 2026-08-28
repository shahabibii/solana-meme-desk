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
BALANCE_EPS = 1e-9


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
    known_balances: dict[str, float],
    retries: int = 5,
    delay_sec: float = 4.0,
) -> list[tuple[str, float]]:
    """Poll until a new mint appears or an existing balance increases."""
    found: list[tuple[str, float]] = []
    baseline = dict(known_balances)
    for attempt in range(retries):
        if attempt:
            await asyncio.sleep(delay_sec)
        holdings = await wallet_mints_with_balance(api_key, wallet)
        for mint, amt in holdings.items():
            if mint == USDC_MINT:
                continue
            prev = baseline.get(mint, 0.0)
            if amt > prev + BALANCE_EPS:
                found.append((mint, amt - prev))
                baseline[mint] = amt
        if found:
            log.info(
                "fomo relay resolved %s mint(s) for %s after %s tries",
                len(found),
                wallet[:8],
                attempt + 1,
            )
            return found
    return found


async def mints_from_txs_after_relay(
    api_key: str,
    wallet: str,
    *,
    after_ts: int,
    watched: set[str],
) -> list[tuple[str, float]]:
    """Fallback: scan address history for token receipts after relay timestamp."""
    from orchestrator.feeds.helius_wallets import parse_helius_swap

    if not api_key or not after_ts:
        return []
    url = (
        f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
        f"?api-key={api_key}&limit=25"
    )
    found: list[tuple[str, float]] = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            for tx in resp.json():
                if not isinstance(tx, dict):
                    continue
                ts = int(tx.get("timestamp") or 0)
                if ts and ts < after_ts - 2:
                    continue
                parsed = parse_helius_swap(tx, watched)
                if parsed and parsed.get("side") == "buy":
                    mint = str(parsed.get("mint") or "")
                    if mint and mint != USDC_MINT:
                        found.append((mint, 0.0))
                for acc in tx.get("accountData") or []:
                    if acc.get("account") != wallet:
                        continue
                    for ch in acc.get("tokenBalanceChanges") or []:
                        mint = str(ch.get("mint") or "")
                        if not mint or mint == USDC_MINT:
                            continue
                        raw = (ch.get("rawTokenAmount") or {}).get("tokenAmount", "0")
                        try:
                            delta = int(str(raw))
                        except (TypeError, ValueError):
                            delta = 0
                        if delta > 0:
                            found.append((mint, float(delta)))
    except Exception as exc:
        log.warning("fomo relay tx scan %s: %s", wallet[:8], exc)
    # dedupe preserving order
    seen: set[str] = set()
    out: list[tuple[str, float]] = []
    for mint, amt in found:
        if mint in seen:
            continue
        seen.add(mint)
        out.append((mint, amt))
    return out


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
            "relay_ts": int(tx.get("timestamp") or 0),
        }
    return None
