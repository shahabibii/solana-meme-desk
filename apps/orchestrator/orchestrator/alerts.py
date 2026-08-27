"""Outbound alerts — Slack or Discord incoming webhooks."""

from __future__ import annotations

import logging
import re

import httpx

log = logging.getLogger(__name__)

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _format_for_slack(message: str) -> str:
    """Discord-style **bold** → Slack mrkdwn *bold*."""
    return _BOLD_RE.sub(r"*\1*", message[:3900])


def _payload(webhook_url: str, message: str) -> dict[str, str]:
    url = webhook_url.lower()
    if "hooks.slack.com" in url:
        return {"text": _format_for_slack(message)}
    return {"content": message[:1900]}


async def send_alert(webhook_url: str | None, message: str) -> None:
    if not webhook_url or not message.strip():
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(webhook_url, json=_payload(webhook_url, message))
            if r.status_code >= 400:
                log.warning("alert webhook %s: %s", r.status_code, r.text[:120])
    except Exception as exc:
        log.warning("alert send failed: %s", exc)
