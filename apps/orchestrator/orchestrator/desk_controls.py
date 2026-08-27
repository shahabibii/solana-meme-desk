"""Persisted desk controls (pause / kill switch)."""

from __future__ import annotations

import json
from pathlib import Path


class DeskControls:
    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / "desk_controls.json"
        self._paused = False
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._paused = bool(data.get("paused"))
        except Exception:
            self._paused = False

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({"paused": self._paused}))

    @property
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, value: bool) -> None:
        self._paused = value
        self._save()
