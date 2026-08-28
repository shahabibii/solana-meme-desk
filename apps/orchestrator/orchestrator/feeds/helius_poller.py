"""Poll Helius address history — backup when webhooks miss UNKNOWN / misconfigured."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

import httpx

from orchestrator.feeds.helius_wallets import parse_helius_swap

log = logging.getLogger(__name__)

HELIUS_ADDR_TX = "https://api.helius.xyz/v0/addresses/{address}/transactions"


async def poll_wallet_trades(
    *,
    api_key: str,
    wallets_getter: Callable[[], list[str]],
    on_trade: Callable[[dict[str, Any]], Awaitable[None]],
    seen: dict[str, set[str]],
    running: Callable[[], bool],
    interval_sec: float = 12.0,
    limit: int = 25,
    on_status: Callable[[str, str], None] | None = None,
) -> None:
    """Poll recent txs per watched wallet; parse buys/sells webhooks may miss."""
    if not api_key:
        while running():
            await asyncio.sleep(30)
        return

    url_tpl = HELIUS_ADDR_TX + f"?api-key={api_key}&limit={limit}"
    bootstrapped = False
    rate_limited_until = 0.0

    while running():
        now = asyncio.get_event_loop().time()
        if now < rate_limited_until:
            if on_status:
                on_status("error", "helius_rate_limited")
            await asyncio.sleep(min(60.0, rate_limited_until - now + 1))
            continue

        wallets = sorted({w for w in wallets_getter() if w})
        watched = set(wallets)
        if not watched:
            await asyncio.sleep(interval_sec)
            continue
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for addr in wallets:
                    if not running():
                        break
                    try:
                        resp = await client.get(url_tpl.format(address=addr))
                        if resp.status_code == 429 or "max usage" in (resp.text or "").lower():
                            log.warning(
                                "helius poller rate-limited/exhausted — backing off 15m"
                            )
                            rate_limited_until = asyncio.get_event_loop().time() + 900
                            if on_status:
                                on_status("error", "helius_rate_limited")
                            break
                        if resp.status_code != 200:
                            log.warning(
                                "helius poller %s HTTP %s: %s",
                                addr[:8],
                                resp.status_code,
                                (resp.text or "")[:80],
                            )
                            if on_status:
                                on_status("error", f"http_{resp.status_code}")
                            continue
                        txs = resp.json()
                        if not isinstance(txs, list):
                            continue
                        bucket = seen.setdefault(addr, set())
                        if not bootstrapped:
                            for tx in txs:
                                sig = str((tx or {}).get("signature") or "")
                                if sig:
                                    bucket.add(sig)
                            continue
                        for tx in txs:
                            if not isinstance(tx, dict):
                                continue
                            sig = str(tx.get("signature") or "")
                            if not sig or sig in bucket:
                                continue
                            bucket.add(sig)
                            if len(bucket) > 500:
                                bucket.clear()
                                bucket.add(sig)
                            parsed = parse_helius_swap(tx, watched)
                            if parsed:
                                log.info(
                                    "helius poller: %s %s %s sig=%s",
                                    parsed.get("side"),
                                    parsed.get("trader", "")[:8],
                                    str(parsed.get("mint", ""))[:8],
                                    sig[:16],
                                )
                                if on_status:
                                    on_status("ok", f"helius · {len(wallets)} wallets")
                                await on_trade(parsed)
                    except Exception as exc:
                        log.debug("helius poller %s: %s", addr[:8], exc)
                    await asyncio.sleep(0.25)
            bootstrapped = True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("helius poller loop: %s", exc)
        await asyncio.sleep(interval_sec)
