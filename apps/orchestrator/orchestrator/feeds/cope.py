"""Cope Capital API — fomo.family smart money (optional API key)."""

from __future__ import annotations

import re
from typing import Any

import httpx

from orchestrator.models import MintCandidate

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
            } and isinstance(val, str):
                if _looks_like_wallet(val) and val not in into:
                    into.append(val)
                continue
            _extract_wallets(val, into=into, depth=depth + 1)


class CopeClient:
    BASE = "https://api.cope.capital/v1"

    def __init__(self, api_key: str | None = None) -> None:
        self._key = api_key
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    async def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        if not self.enabled:
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{self.BASE}{path}",
                    headers=self._headers,
                    params=params or {},
                )
                if r.status_code in (401, 404):
                    return None
                r.raise_for_status()
                return r.json()
        except Exception:
            return None

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

    async def top_traders(self, limit: int = 20) -> list[str]:
        """Resolve wallet addresses for copy-trading watchlist."""
        wallets: list[str] = []
        for path in (
            "/traders/top",
            "/traders",
            "/watchlist",
            "/traders/hot",
            "/wallets/top",
            "/smart-money",
            "/leaders",
        ):
            data = await self._get_json(path, params={"limit": limit})
            if not data:
                continue
            _extract_wallets(data, into=wallets)
            if wallets:
                break

        # Fallback: scrape wallets embedded in hot/convergence payloads.
        if len(wallets) < limit:
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
        return out
