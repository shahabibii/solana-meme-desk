"""Optional LLM summaries for Research agent."""

from __future__ import annotations

import httpx


async def llm_research_summary(
    *,
    api_key: str,
    mint: str,
    symbol: str,
    source: str,
    thesis: str,
    safety_score: int,
    model: str = "gpt-4o-mini",
) -> str | None:
    prompt = (
        f"Solana meme coin desk research (one sentence, trader tone):\n"
        f"mint={mint[:12]}… symbol={symbol} source={source} safety={safety_score}\n"
        f"context: {thesis}\n"
        f"Verdict line only — no disclaimer."
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are Onyx research for a Solana meme desk."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 80,
                    "temperature": 0.4,
                },
            )
            if r.status_code >= 400:
                return None
            data = r.json()
            text = (
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            ).strip()
            return text[:240] or None
    except Exception:
        return None
