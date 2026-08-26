"""Orchestrator tests."""

from orchestrator.execution.paper import PaperBook


def test_paper_buy_sell() -> None:
    book = PaperBook.new(1.0)
    assert book.buy("mint1", "PEPE", 0.1)
    assert book.cash_sol == 0.9
    assert book.equity_sol == 1.0
    proceeds = book.sell("mint1")
    assert proceeds is not None
    assert "mint1" not in book.positions
