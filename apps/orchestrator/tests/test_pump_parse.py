"""PumpPortal message parsing."""

from orchestrator.feeds.pumpportal import parse_new_token_message


def test_parse_new_token() -> None:
    raw = {"mint": "7xKXtg2CW87d97TXJSDpbD6j9fj1aR8P8" + "A" * 12, "symbol": "PEPE", "name": "Pepe"}
    c = parse_new_token_message(raw)
    assert c is not None
    assert c.symbol == "PEPE"
    assert c.source == "pump"
