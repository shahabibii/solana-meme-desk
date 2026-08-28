"""Tests for live position persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from orchestrator.live_positions import LivePositionStore


def test_live_position_roundtrip(tmp_path: Path) -> None:
    store = LivePositionStore(tmp_path / "live_positions.json")
    tracks = {
        "mint1234567890123456789012345678901234567890": {
            "symbol": "TEST",
            "entry_sol": 0.07,
            "entry_ts": datetime(2026, 8, 28, 4, 0, tzinfo=timezone.utc),
            "source": "copy",
            "venue": "jupiter",
            "peak_pnl_pct": 5.0,
            "entry_price": 0.001,
            "tp_hit": {50.0},
        }
    }
    store.save(tracks)
    loaded = store.load()
    mint = "mint1234567890123456789012345678901234567890"
    assert loaded[mint]["symbol"] == "TEST"
    assert loaded[mint]["entry_sol"] == 0.07
    assert loaded[mint]["tp_hit"] == {50.0}
