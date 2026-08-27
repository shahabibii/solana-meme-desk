"""Outbound alerts — Discord webhook (works with Discord or generic JSON POST)."""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


async def send_alert(webhook_url: str | None, message: str) -> None:
    if not webhook_url or not message.strip():
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(webhook_url, json={"content": message[:1900]})
            if r.status_code >= 400:
                log.warning("alert webhook %s: %s", r.status_code, r.text[:120])
    except Exception as exc:
        log.warning("alert send failed: %s", exc)
