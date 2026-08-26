"""Backtest from journal."""

from __future__ import annotations

from pathlib import Path

from orchestrator.agents.backtest import run_backtest
from orchestrator.journal.store import JournalStore


def test_backtest_empty(tmp_path: Path) -> None:
    j = JournalStore(tmp_path / "t.db")
    result = run_backtest(j)
    assert result["round_trips"] == 0


def test_backtest_round_trips(tmp_path: Path) -> None:
    j = JournalStore(tmp_path / "t.db")
    j.record_trade(
        mint="mint111111111111111111111111111111111",
        symbol="A",
        side="buy",
        sol=0.05,
        pnl_pct=None,
        mode="paper",
        source="pump",
    )
    j.record_trade(
        mint="mint111111111111111111111111111111111",
        symbol="A",
        side="sell",
        sol=0.06,
        pnl_pct=20.0,
        mode="paper",
        source="pump",
    )
    result = run_backtest(j)
    assert result["round_trips"] == 1
    assert result["win_rate"] == 1.0
