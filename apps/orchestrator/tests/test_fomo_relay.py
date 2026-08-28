"""fomo.family USDC relay detection."""

from orchestrator.feeds.copy_filters import USDC_MINT
from orchestrator.feeds.fomo_relay import FOMO_USDC_ROUTERS, parse_fomo_usdc_relay
from orchestrator.feeds.helius_wallets import parse_helius_swap

ROWDY = "CzU8MaRcwvwUoNkwJFLbvtFWJugcEXAhDDQqNFE4ybb7"
ROUTER = next(iter(FOMO_USDC_ROUTERS))


def test_fomo_usdc_relay_detected() -> None:
    tx = {
        "type": "UNKNOWN",
        "source": "UNKNOWN",
        "signature": "relay123",
        "tokenTransfers": [
            {
                "fromUserAccount": ROWDY,
                "toUserAccount": ROUTER,
                "mint": USDC_MINT,
                "tokenAmount": 5000.0,
            }
        ],
    }
    relay = parse_fomo_usdc_relay(tx, {ROWDY})
    assert relay is not None
    assert relay["fomo_relay"] is True
    assert relay["trader"] == ROWDY
    assert relay["trader_usdc"] == 5000.0
    assert relay.get("trader_sol")


def test_fomo_relay_wired_into_helius_parser() -> None:
    tx = {
        "type": "UNKNOWN",
        "signature": "relay456",
        "tokenTransfers": [
            {
                "fromUserAccount": ROWDY,
                "toUserAccount": ROUTER,
                "mint": USDC_MINT,
                "tokenAmount": 100.0,
            }
        ],
    }
    parsed = parse_helius_swap(tx, {ROWDY})
    assert parsed is not None
    assert parsed.get("fomo_relay") is True


def test_skips_failed_tx() -> None:
    tx = {
        "type": "SWAP",
        "source": "JUPITER",
        "transactionError": {"error": "failed"},
        "events": {
            "swap": {
                "nativeInput": {"account": ROWDY, "amount": "1000000000"},
                "tokenOutputs": [{"userAccount": ROWDY, "mint": "x" * 44, "rawTokenAmount": {"tokenAmount": "1"}}],
            }
        },
    }
    assert parse_helius_swap(tx, {ROWDY}) is None
