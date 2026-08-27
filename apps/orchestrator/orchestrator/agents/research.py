"""Research agent — Cope thesis + metadata summary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from orchestrator.models import MintCandidate


@dataclass
class ResearchReport:
    thesis: str
    detail: str
    ms: int = 0

    @property
    def verdict(self) -> str:
        return "PASS"


async def fetch_thesis(api_key: str | None, mint: str) -> str | None:
    if not api_key:
        return None
    headers = {"Authorization": f"Bearer {api_key}"}
    paths = (
        f"https://api.cope.capital/v1/tokens/{mint}/thesis",
        f"https://api.cope.capital/v1/token/{mint}/thesis",
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in paths:
            try:
                r = await client.get(url, headers=headers)
                if r.status_code == 404:
                    continue
                if r.status_code == 401:
                    return None
                r.raise_for_status()
                data = r.json()
                if isinstance(data, str):
                    return data[:240]
                if isinstance(data, dict):
                    return str(
                        data.get("thesis")
                        or data.get("summary")
                        or data.get("text")
                        or ""
                    )[:240] or None
            except Exception:
                continue
    return None


def thesis_from_meta(candidate: MintCandidate) -> str:
    meta = candidate.meta or {}
    if candidate.source == "convergence":
        conv = meta.get("convergence") or {}
        wallets = conv.get("wallets") or conv.get("traders") or conv.get("count")
        if wallets:
            return f"convergence: {wallets} wallets"
    if candidate.source == "fomo":
        hot = meta.get("hot") or {}
        rank = hot.get("rank") or hot.get("score")
        if rank:
            return f"fomo hot rank {rank}"
    if candidate.source == "copy":
        trader = meta.get("trader") or "unknown"
        return f"wallet mirror {str(trader)[:8]}…"
    if candidate.source == "pump":
        return "pump_launch"
    return candidate.source


async def run_research(
    candidate: MintCandidate,
    *,
    cope_api_key: str | None,
    openai_api_key: str | None = None,
    llm_enabled: bool = False,
    safety_score: int = 0,
    openai_model: str = "gpt-4o-mini",
) -> ResearchReport:
    import time

    t0 = time.perf_counter()
    thesis = await fetch_thesis(cope_api_key, candidate.mint)
    if not thesis:
        thesis = thesis_from_meta(candidate)

    if llm_enabled and openai_api_key:
        from orchestrator.agents.research_llm import llm_research_summary

        llm = await llm_research_summary(
            api_key=openai_api_key,
            mint=candidate.mint,
            symbol=candidate.symbol,
            source=candidate.source,
            thesis=thesis,
            safety_score=safety_score,
            model=openai_model,
        )
        if llm:
            thesis = llm

    ms = int((time.perf_counter() - t0) * 1000)
    return ResearchReport(thesis=thesis, detail=thesis[:120], ms=ms)
