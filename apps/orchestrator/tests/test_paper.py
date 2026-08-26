"""Orchestrator tests."""

from orchestrator.execution.paper import PaperBook, RiskLimits


def test_paper_buy_sell_pnl() -> None:
    book = PaperBook.new(1.0, RiskLimits())
    assert book.buy("mint1", "PEPE", 0.04, 0.001)
    book.mark_price("mint1", 0.0015)  # +50%
    result = book.sell("mint1")
    assert result is not None
    proceeds, pct = result
    assert pct > 40
    assert proceeds > 0.05
