"""Solana RPC wallet poller — fallback when Helius enhanced API is rate-limited."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

import httpx

from orchestrator.feeds.copy_filters import COPY_SKIP_MINTS, is_copyable_mint

log = logging.getLogger(__name__)

FALLBACK_RPC = "https://api.mainnet-beta.solana.com"


def _pubkey(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("pubkey") or "")
    return str(entry or "")


def parse_rpc_token_delta(tx: dict[str, Any], trader: str) -> dict[str, Any] | None:
    """Detect meme buy/sell from pre/post token balances for a watched wallet."""
    meta = tx.get("meta") or {}
    if meta.get("err"):
        return None

    nets: dict[str, float] = {}
    for entry in meta.get("postTokenBalances") or []:
        if str(entry.get("owner") or "") != trader:
            continue
        mint = str(entry.get("mint") or "")
        amt = float(((entry.get("uiTokenAmount") or {}).get("uiAmount")) or 0)
        nets[mint] = nets.get(mint, 0.0) + amt
    for entry in meta.get("preTokenBalances") or []:
        if str(entry.get("owner") or "") != trader:
            continue
        mint = str(entry.get("mint") or "")
        amt = float(((entry.get("uiTokenAmount") or {}).get("uiAmount")) or 0)
        nets[mint] = nets.get(mint, 0.0) - amt

    best_buy: tuple[str, float] | None = None
    best_sell: tuple[str, float] | None = None
    for mint, delta in nets.items():
        if mint in COPY_SKIP_MINTS or not is_copyable_mint(mint):
            continue
        if delta > 1.0 and (best_buy is None or delta > best_buy[1]):
            best_buy = (mint, delta)
        elif delta < -1.0 and (best_sell is None or abs(delta) > best_sell[1]):
            best_sell = (mint, abs(delta))

    # Approximate SOL spent from native balance change of trader.
    trader_sol: float | None = None
    msg = (tx.get("transaction") or {}).get("message") or {}
    keys = [_pubkey(k) for k in (msg.get("accountKeys") or [])]
    if trader in keys:
        idx = keys.index(trader)
        pre = meta.get("preBalances") or []
        post = meta.get("postBalances") or []
        if idx < len(pre) and idx < len(post):
            lamports = pre[idx] - post[idx]
            if lamports > 50_000:
                trader_sol = round(lamports / 1_000_000_000.0, 4)

    sig = str(((tx.get("transaction") or {}).get("signatures") or [None])[0] or "")
    if best_buy:
        mint, _ = best_buy
        return {
            "side": "buy",
            "mint": mint,
            "trader": trader,
            "trader_sol": trader_sol,
            "venue": "RPC",
            "via": "solana_rpc",
            "signature": sig,
            "symbol": mint[:8].upper(),
        }
    if best_sell:
        mint, _ = best_sell
        return {
            "side": "sell",
            "mint": mint,
            "trader": trader,
            "venue": "RPC",
            "via": "solana_rpc",
            "signature": sig,
            "symbol": mint[:8].upper(),
        }
    return None


async def poll_wallet_trades_rpc(
    *,
    rpc_url: str,
    wallets_getter: Callable[[], list[str]],
    on_trade: Callable[[dict[str, Any]], Awaitable[None]],
    seen: dict[str, set[str]],
    running: Callable[[], bool],
    interval_sec: float = 8.0,
    limit: int = 12,
    on_status: Callable[[str, str], None] | None = None,
) -> None:
    """Poll getSignaturesForAddress + getTransaction for watched wallets."""
    rpc = rpc_url or FALLBACK_RPC

    async def _rpc(client: httpx.AsyncClient, method: str, params: list[Any]) -> Any:
        resp = await client.post(
            rpc,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("error"):
            return None
        return data.get("result")

    bootstrapped = False
    while running():
        wallets = sorted({w for w in wallets_getter() if w})
        if not wallets:
            await asyncio.sleep(interval_sec)
            continue
        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                # Prefer public RPC if configured Helius RPC is also exhausted.
                endpoints = [rpc]
                if rpc != FALLBACK_RPC:
                    endpoints.append(FALLBACK_RPC)
                active_rpc = endpoints[0]

                for addr in wallets:
                    if not running():
                        break
                    try:
                        sigs = None
                        for endpoint in endpoints:
                            active_rpc = endpoint
                            resp = await client.post(
                                endpoint,
                                json={
                                    "jsonrpc": "2.0",
                                    "id": 1,
                                    "method": "getSignaturesForAddress",
                                    "params": [addr, {"limit": limit}],
                                },
                            )
                            if resp.status_code == 200 and not (resp.json() or {}).get("error"):
                                sigs = (resp.json() or {}).get("result") or []
                                break
                        if sigs is None:
                            continue

                        bucket = seen.setdefault(addr, set())
                        if not bootstrapped:
                            for item in sigs:
                                sig = str((item or {}).get("signature") or "")
                                if sig:
                                    bucket.add(sig)
                            continue

                        for item in sigs:
                            if not isinstance(item, dict) or item.get("err"):
                                continue
                            sig = str(item.get("signature") or "")
                            if not sig or sig in bucket:
                                continue
                            bucket.add(sig)
                            if len(bucket) > 500:
                                bucket.clear()
                                bucket.add(sig)

                            tx = None
                            for endpoint in endpoints:
                                resp = await client.post(
                                    endpoint,
                                    json={
                                        "jsonrpc": "2.0",
                                        "id": 1,
                                        "method": "getTransaction",
                                        "params": [
                                            sig,
                                            {
                                                "encoding": "jsonParsed",
                                                "maxSupportedTransactionVersion": 0,
                                            },
                                        ],
                                    },
                                )
                                if resp.status_code == 200:
                                    body = resp.json() or {}
                                    if not body.get("error"):
                                        tx = body.get("result")
                                        if tx:
                                            break
                            if not tx:
                                continue
                            parsed = parse_rpc_token_delta(tx, addr)
                            if not parsed:
                                continue
                            log.info(
                                "rpc poller: %s %s %s sig=%s",
                                parsed.get("side"),
                                addr[:8],
                                str(parsed.get("mint", ""))[:8],
                                sig[:16],
                            )
                            if on_status:
                                on_status("ok", f"rpc · {len(wallets)} wallets")
                            await on_trade(parsed)
                    except Exception as exc:
                        log.debug("rpc poller %s: %s", addr[:8], exc)
                    await asyncio.sleep(0.12)
                if on_status:
                    on_status("ok", f"rpc:{active_rpc.split('//')[-1][:24]} · {len(wallets)} wallets")
            bootstrapped = True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("rpc poller loop: %s", exc)
            if on_status:
                on_status("error", str(exc)[:80])
        await asyncio.sleep(interval_sec)
