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

    async def hot_tokens(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{self.BASE}/tokens/hot",
                    headers=self._headers,
                    params={"limit": limit},
                )
                if r.status_code == 401:
                    return []
                r.raise_for_status()
                data = r.json()
                return data if isinstance(data, list) else (data.get("tokens") or [])
        except Exception:
            return []

    async def convergence(self, limit: int = 10) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{self.BASE}/convergence",
                    headers=self._headers,
                    params={"limit": limit},
                )
                if r.status_code == 401:
                    return []
                r.raise_for_status()
                data = r.json()
                return data if isinstance(data, list) else (data.get("events") or [])
        except Exception:
            return []

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
