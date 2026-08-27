"""ElevenLabs TTS — Maisie (friendly casual neighbor)."""

from __future__ import annotations

import httpx

from orchestrator.config import settings

MAISIE_VOICE_ID = "QtY3JBOUKEB5xzrRfOKc"
MAISIE_NAME = "Maisie"
MAISIE_MODEL = "eleven_flash_v2_5"
PREVIEW_PATH = "/voices/maisie-preview.mp3"


def voice_info() -> dict[str, object]:
    active = bool(settings.elevenlabs_api_key)
    return {
        "name": MAISIE_NAME,
        "label": "Maisie — friendly casual neighbor",
        "voice_id": settings.elevenlabs_voice_id or MAISIE_VOICE_ID,
        "provider": "elevenlabs" if active else "browser",
        "active": active,
        "preview_url": PREVIEW_PATH,
    }


async def synthesize_maisie(text: str) -> bytes:
    if not settings.elevenlabs_api_key:
        raise RuntimeError("ElevenLabs API key not configured")

    voice_id = settings.elevenlabs_voice_id or MAISIE_VOICE_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = {
        "text": text,
        "model_id": settings.elevenlabs_model or MAISIE_MODEL,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.8,
            "style": 0.35,
            "use_speaker_boost": True,
        },
    }
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            detail = resp.text[:200]
            raise RuntimeError(f"ElevenLabs TTS failed ({resp.status_code}): {detail}")
        return resp.content
