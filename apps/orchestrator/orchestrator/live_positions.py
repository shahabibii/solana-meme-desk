"""Persist live position tracks across restarts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _serialize_track(track: dict[str, Any]) -> dict[str, Any]:
    out = dict(track)
    ts = out.get("entry_ts")
    if isinstance(ts, datetime):
        out["entry_ts"] = ts.isoformat()
    tp = out.get("tp_hit")
    if isinstance(tp, set):
        out["tp_hit"] = sorted(tp)
    return out


def _deserialize_track(raw: dict[str, Any]) -> dict[str, Any]:
    out = dict(raw)
    ts = out.get("entry_ts")
    if isinstance(ts, str):
        out["entry_ts"] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    tp = out.get("tp_hit")
    if isinstance(tp, list):
        out["tp_hit"] = set(float(x) for x in tp)
    elif tp is None:
        out["tp_hit"] = set()
    return out


class LivePositionStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text())
            positions = raw.get("positions") or {}
            return {mint: _deserialize_track(track) for mint, track in positions.items()}
        except Exception:
            return {}

    def save(self, tracks: dict[str, dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_ts": datetime.now(timezone.utc).isoformat(),
            "positions": {mint: _serialize_track(track) for mint, track in tracks.items()},
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        tmp.replace(self._path)
