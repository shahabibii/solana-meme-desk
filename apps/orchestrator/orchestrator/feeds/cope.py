"""Cope Capital API — fomo.family smart money (optional API key)."""

from __future__ import annotations

from typing import Any

import httpx

from orchestrator.models import MintCandidate


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
        for path in ("/traders/top", "/watchlist", "/traders/hot", "/wallets/top"):
            data = await self._get_json(path, params={"limit": limit})
            if not data:
                continue
            items = data if isinstance(data, list) else (data.get("traders") or data.get("wallets") or data.get("data") or [])
            for item in items:
                if isinstance(item, str) and len(item) >= 32:
                    wallets.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                w = (
                    item.get("wallet")
                    or item.get("address")
                    or item.get("pubkey")
                    or item.get("trader")
                    or item.get("publicKey")
                )
                if w and len(str(w)) >= 32:
                    wallets.append(str(w))
            if wallets:
                break
        # dedupe preserve order
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
