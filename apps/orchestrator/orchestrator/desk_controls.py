"""Persisted desk controls (pause + mode survive Fly restarts)."""

from __future__ import annotations

import json
from pathlib import Path


class DeskControls:
    def __init__(self, data_dir: Path, default_mode: str = "paper") -> None:
        self._path = data_dir / "desk_controls.json"
        self._paused = False
        self._mode: str | None = None
        self._default_mode = default_mode if default_mode in ("paper", "live") else "paper"
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._paused = bool(data.get("paused"))
            raw = data.get("mode")
            if raw in ("paper", "live"):
                self._mode = raw
        except Exception:
            self._paused = False
            self._mode = None

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {"paused": self._paused}
        if self._mode is not None:
            payload["mode"] = self._mode
        self._path.write_text(json.dumps(payload))

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def mode(self) -> str | None:
        return self._mode

    def initial_mode(self, live_ready: bool) -> str:
        want = self._mode if self._mode is not None else self._default_mode
        if want == "live" and not live_ready:
            return "paper"
        return want

    def set_paused(self, value: bool) -> None:
        self._paused = value
        self._save()

    def set_mode(self, mode: str) -> None:
        if mode not in ("paper", "live"):
            return
        self._mode = mode
        self._save()
