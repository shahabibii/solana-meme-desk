"""Cope Capital API — fomo.family smart money (optional API key)."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

from orchestrator.models import MintCandidate

logger = logging.getLogger(__name__)

# Solana base58 pubkeys are typically 32–44 chars.
_WALLET_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_SKIP_KEYS = frozenset({"mint", "token", "tokenAddress", "symbol", "ticker", "name"})


def _looks_like_wallet(value: str) -> bool:
    return bool(_WALLET_RE.match(value)) and len(value) >= 32


def _extract_wallets(obj: Any, *, into: list[str], depth: int = 0) -> None:
    if depth > 6 or len(into) >= 40:
        return
    if isinstance(obj, str):
        if _looks_like_wallet(obj) and obj not in into:
            into.append(obj)
        return
    if isinstance(obj, list):
        for item in obj:
            _extract_wallets(item, into=into, depth=depth + 1)
        return
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in _SKIP_KEYS and isinstance(val, str):
                continue
            if key.lower() in {
                "wallet",
                "address",
                "pubkey",
                "trader",
                "publickey",
                "owner",
                "signer",
                "user",
                "account",
                "solana_wallet",
                "wallet_address",
            } and isinstance(val, str):
                if _looks_like_wallet(val) and val not in into:
                    into.append(val)
                continue
            _extract_wallets(val, into=into, depth=depth + 1)


def _as_list(data: Any, *keys: str) -> list[Any]:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in keys:
            v = data.get(k)
            if isinstance(v, list):
                return v
        return [data]
    return []


class CopeClient:
    BASE = os.environ.get("COPE_API_BASE", "https://api.cope.capital/v1")

    def __init__(self, api_key: str | None = None) -> None:
        self._key = api_key
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._handles: list[str] = []
        self._manual_handles: list[str] = []
        self.last_error: str | None = None

    def set_manual_handles(self, handles: list[str]) -> None:
        seen: set[str] = set()
        out: list[str] = []
        for h in handles:
            clean = str(h).strip().lstrip("@")
            if clean and clean not in seen:
                seen.add(clean)
                out.append(clean)
        self._manual_handles = out
        if out:
            self._merge_handles(out)

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def _fail(self, detail: str) -> None:
        self.last_error = detail
        logger.warning("cope: %s", detail)

    async def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        if not self.enabled:
            self._fail("COPE_API_KEY not configured")
            return None
        url = f"{self.BASE}{path}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(url, headers=self._headers, params=params or {})
                if r.status_code in (401, 404, 402):
                    self._fail(f"GET {path} -> HTTP {r.status_code}")
                    return None
                r.raise_for_status()
                self.last_error = None
                return r.json()
        except httpx.ConnectError as exc:
            self._fail(f"GET {path} connect error: {exc}")
            return None
        except httpx.HTTPStatusError as exc:
            self._fail(f"GET {path} -> HTTP {exc.response.status_code}")
            return None
        except Exception as exc:
            self._fail(f"GET {path} failed: {exc}")
            return None

    async def _post_json(self, path: str, body: dict[str, Any]) -> Any:
        if not self.enabled:
            self._fail("COPE_API_KEY not configured")
            return None
        url = f"{self.BASE}{path}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(url, headers=self._headers, json=body)
                if r.status_code in (401, 404, 402):
                    self._fail(f"POST {path} -> HTTP {r.status_code}")
                    return None
                r.raise_for_status()
                self.last_error = None
                return r.json()
        except httpx.ConnectError as exc:
            self._fail(f"POST {path} connect error: {exc}")
            return None
        except httpx.HTTPStatusError as exc:
            self._fail(f"POST {path} -> HTTP {exc.response.status_code}")
            return None
        except Exception as exc:
            self._fail(f"POST {path} failed: {exc}")
            return None

    async def health(self) -> dict[str, Any]:
        """Light probe — used by status/setup to explain empty fomo sync."""
        if not self.enabled:
            return {"reachable": False, "error": "COPE_API_KEY not configured"}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(f"{self.BASE}/account/follows", headers=self._headers)
                return {
                    "reachable": True,
                    "status_code": r.status_code,
                    "base": self.BASE,
                }
        except httpx.ConnectError as exc:
            return {
                "reachable": False,
                "error": f"Cannot reach {self.BASE}: {exc}",
                "base": self.BASE,
            }
        except Exception as exc:
            return {"reachable": False, "error": str(exc), "base": self.BASE}

    async def sync_fomo(self, fomo_handle: str) -> dict[str, Any]:
        """Import follows from a fomo.family profile into the Cope account."""
        handle = fomo_handle.strip().lstrip("@")
        data = await self._post_json("/account/sync-fomo", {"fomo_handle": handle})
        if isinstance(data, dict):
            return data
        err = self.last_error or "sync-fomo returned no data"
        return {"ok": False, "handle": handle, "error": err}

    async def follows(self) -> list[str]:
        """Handles you follow on fomo.family (after sync-fomo)."""
        data = await self._get_json("/account/follows")
        handles: list[str] = []
        for item in _as_list(data, "follows", "data", "handles"):
            if isinstance(item, str):
                handles.append(item.lstrip("@"))
            elif isinstance(item, dict):
                h = item.get("handle") or item.get("username") or item.get("name")
                if h:
                    handles.append(str(h).lstrip("@"))
        self._handles = handles
        return handles

    async def leaderboard(self, *, timeframe: str = "7d", limit: int = 20) -> list[dict[str, Any]]:
        data = await self._get_json(
            "/leaderboard", params={"timeframe": timeframe, "limit": limit}
        )
        return _as_list(data, "traders", "leaderboard", "data")

    async def search_traders(
        self, *, chain: str = "solana", limit: int = 20, min_win_rate: float = 55
    ) -> list[dict[str, Any]]:
        data = await self._get_json(
            "/traders/search",
            params={
                "chain": chain,
                "limit": limit,
                "min_win_rate": min_win_rate,
                "sort_by": "pnl",
            },
        )
        return _as_list(data, "traders", "data", "results")

    async def activity(
        self,
        *,
        handle: str | None = None,
        action: str | None = "buy",
        chain: str = "solana",
        since: int | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"chain": chain, "limit": limit}
        if handle:
            params["handle"] = handle.lstrip("@")
        if action:
            params["action"] = action
        if since is not None:
            params["since"] = since
        data = await self._get_json("/activity", params=params)
        return _as_list(data, "activity", "events", "data", "trades")

    async def hot_tokens(self, limit: int = 10) -> list[dict[str, Any]]:
        data = await self._get_json("/tokens/hot", params={"limit": limit})
        if data is None:
            return []
        return data if isinstance(data, list) else (data.get("tokens") or data.get("data") or [])

    async def convergence(self, limit: int = 10) -> list[dict[str, Any]]:
        data = await self._get_json("/convergence", params={"limit": limit})
        if data is None:
            return []
        return data if isinstance(data, list) else (data.get("events") or data.get("data") or [])

    def _handles_from_rows(self, rows: list[Any]) -> list[str]:
        out: list[str] = []
        for item in rows:
            if isinstance(item, str):
                out.append(item.lstrip("@"))
            elif isinstance(item, dict):
                h = item.get("handle") or item.get("username") or item.get("name")
                if h:
                    out.append(str(h).lstrip("@"))
        return out

    def _merge_handles(self, handles: list[str]) -> list[str]:
        seen = {h.lstrip("@") for h in self._handles}
        out = list(self._handles)
        for h in handles:
            clean = h.lstrip("@")
            if clean and clean not in seen:
                seen.add(clean)
                out.append(clean)
        self._handles = out
        return out

    async def resolve_handles(self) -> list[str]:
        """Manual follows first, then Cope account follows, else leaderboard fallback."""
        if self._manual_handles:
            self._merge_handles(self._manual_handles)
        api_follows = await self.follows()
        if api_follows:
            self._merge_handles(api_follows)
        if self._handles:
            return self._handles[:20]
        handles = self._handles_from_rows(await self.leaderboard(timeframe="7d", limit=15))
        if handles:
            return self._merge_handles(handles)[:15]
        handles = self._handles_from_rows(
            await self.search_traders(chain="solana", limit=15, min_win_rate=55)
        )
        return self._merge_handles(handles)[:15]

    async def wallets_for_handles(self, handles: list[str], *, per_handle: int = 3) -> list[str]:
        """Pull Solana wallets from recent activity for each handle."""
        wallets: list[str] = []
        for handle in handles[:12]:
            rows = await self.activity(handle=handle, action=None, chain="solana", limit=per_handle)
            _extract_wallets(rows, into=wallets)
            if len(wallets) >= 30:
                break
        # Also try leaderboard/search payloads for embedded wallets
        _extract_wallets(await self.leaderboard(limit=20), into=wallets)
        _extract_wallets(await self.search_traders(limit=20), into=wallets)
        seen: set[str] = set()
        out: list[str] = []
        for w in wallets:
            if w not in seen:
                seen.add(w)
                out.append(w)
        return out

    async def top_traders(self, limit: int = 20) -> list[str]:
        """Wallet addresses for PumpPortal subscribeAccountTrade."""
        handles = await self.resolve_handles()
        wallets = await self.wallets_for_handles(handles)
        if wallets:
            return wallets[:limit]

        # Fallback scrape from hot/convergence
        for item in await self.convergence(limit=15):
            _extract_wallets(item, into=wallets)
        for item in await self.hot_tokens(limit=15):
            _extract_wallets(item, into=wallets)
        seen: set[str] = set()
        out: list[str] = []
        for w in wallets:
            if w not in seen:
                seen.add(w)
                out.append(w)
        return out[:limit]

    async def poll_follow_buys(self, handles: list[str] | None = None) -> list[MintCandidate]:
        """Enqueue-ready candidates from fomo follows' recent Solana buys."""
        handles = handles or self._handles or await self.resolve_handles()
        out: list[MintCandidate] = []
        seen_mints: set[str] = set()
        for handle in handles[:10]:
            for item in await self.activity(handle=handle, action="buy", chain="solana", limit=5):
                mint = str(
                    item.get("mint")
                    or item.get("token_mint")
                    or item.get("token")
                    or item.get("tokenAddress")
                    or ""
                )
                if len(mint) < 32 or mint in seen_mints:
                    continue
                seen_mints.add(mint)
                sym = str(item.get("symbol") or item.get("ticker") or "FOMO")[:12]
                trader_sol = item.get("sol_amount") or item.get("solAmount")
                usd = item.get("usd_amount") or item.get("usd")
                if trader_sol is None and usd:
                    try:
                        trader_sol = float(usd) / 150.0  # rough SOL estimate
                    except (TypeError, ValueError):
                        trader_sol = None
                wallets: list[str] = []
                _extract_wallets(item, into=wallets)
                out.append(
                    MintCandidate(
                        mint=mint,
                        symbol=sym,
                        name=sym,
                        source="copy",
                        copy_boost=25,
                        meta={
                            "trader": wallets[0] if wallets else handle,
                            "trader_sol": float(trader_sol) if trader_sol is not None else None,
                            "fomo_handle": handle,
                            "trade_event": item,
                        },
                    )
                )
        return out

    async def poll_candidates(self) -> list[MintCandidate]:
        out: list[MintCandidate] = []
        for item in await self.convergence(limit=5):
            mint = str(item.get("mint") or item.get("token") or "")
            if len(mint) < 32:
                continue
            sym = str(item.get("symbol") or item.get("ticker") or "???")[:12]
            out.append(
                MintCandidate(
                    mint=mint,
                    symbol=sym,
                    name=sym,
                    source="convergence",
                    copy_boost=20,
                    meta={"convergence": item},
                )
            )
        for item in await self.hot_tokens(limit=5):
            mint = str(item.get("mint") or item.get("address") or "")
            if len(mint) < 32:
                continue
            sym = str(item.get("symbol") or "HOT")[:12]
            out.append(
                MintCandidate(
                    mint=mint,
                    symbol=sym,
                    name=sym,
                    source="fomo",
                    copy_boost=10,
                    meta={"hot": item},
                )
            )
        # Follow buys (uses counted activity quota — keep light)
        out.extend(await self.poll_follow_buys())
        return out
