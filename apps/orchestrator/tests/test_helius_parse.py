"""Helius enhanced SWAP webhook parsing."""

from orchestrator.feeds.copy_filters import USDC_MINT
from orchestrator.feeds.helius_wallets import parse_helius_swap

WALLET = "J9WiAZKf8JnCkHFL8fLCCXdEgdoLjLRqU2EGsDjdqYga"
TOKEN = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK-like length
OTHER = "HDixbrzwwLXczhDBk1JVrurPQsuLE8FUKnW2pucSXN3o"


def test_jupiter_buy_via_events_swap() -> None:
    tx = {
        "type": "SWAP",
        "source": "JUPITER",
        "signature": "abc123",
        "description": f"{WALLET[:8]} swapped 1.5 SOL for 225.5 USDC on Jupiter",
        "feePayer": WALLET,
        "events": {
            "swap": {
                "nativeInput": {"account": WALLET, "amount": "1500000000"},
                "tokenOutputs": [
                    {
                        "userAccount": WALLET,
                        "mint": TOKEN,
                        "rawTokenAmount": {"tokenAmount": "225500000", "decimals": 6},
                    }
                ],
                "tokenInputs": [],
            }
        },
    }
    parsed = parse_helius_swap(tx, {WALLET})
    assert parsed is not None
    assert parsed["side"] == "buy"
    assert parsed["mint"] == TOKEN
    assert parsed["trader"] == WALLET
    assert parsed["trader_sol"] == 1.5
    assert parsed["venue"] == "JUPITER"


def test_jupiter_sell_via_token_inputs() -> None:
    tx = {
        "type": "SWAP",
        "source": "JUPITER",
        "signature": "sell123",
        "feePayer": WALLET,
        "events": {
            "swap": {
                "tokenInputs": [
                    {
                        "userAccount": WALLET,
                        "mint": TOKEN,
                        "rawTokenAmount": {"tokenAmount": "1000000", "decimals": 6},
                    }
                ],
                "nativeOutput": {"account": WALLET, "amount": "500000000"},
                "tokenOutputs": [],
            }
        },
    }
    parsed = parse_helius_swap(tx, {WALLET})
    assert parsed is not None
    assert parsed["side"] == "sell"
    assert parsed["mint"] == TOKEN
    assert parsed["trader"] == WALLET


def test_token_transfer_fallback_buy() -> None:
    tx = {
        "type": "SWAP",
        "source": "RAYDIUM",
        "signature": "ray1",
        "feePayer": WALLET,
        "nativeTransfers": [
            {"fromUserAccount": WALLET, "toUserAccount": OTHER, "amount": 80000000},
        ],
        "tokenTransfers": [
            {
                "fromUserAccount": OTHER,
                "toUserAccount": WALLET,
                "mint": TOKEN,
                "tokenAmount": 500000.0,
            }
        ],
    }
    parsed = parse_helius_swap(tx, {WALLET})
    assert parsed is not None
    assert parsed["side"] == "buy"
    assert parsed["mint"] == TOKEN
    assert parsed["trader_sol"] == 0.08


def test_transfer_in_pump_token() -> None:
    pump = "3Atv2msRFLpgPTKHxALnKWTNXrbgCvg4TWZdCHYZpump"
    tx = {
        "type": "TRANSFER",
        "source": "SOLANA_PROGRAM_LIBRARY",
        "signature": "xfer1",
        "tokenTransfers": [
            {
                "fromUserAccount": OTHER,
                "toUserAccount": WALLET,
                "mint": pump,
                "tokenAmount": 100000.0,
            }
        ],
    }
    parsed = parse_helius_swap(tx, {WALLET})
    assert parsed is not None
    assert parsed["side"] == "buy"
    assert parsed["mint"] == pump


def test_jupiter_swap_picks_meme_over_usdc_noise() -> None:
    pump = "4PFGKQbJYRZbk8SHNzqQf4DcpyrKJ7r5UKwj4f37pump"
    tx = {
        "type": "SWAP",
        "source": "JUPITER",
        "signature": "jupmulti",
        "events": {"swap": {"tokenInputs": [], "tokenOutputs": []}},
        "tokenTransfers": [
            {
                "fromUserAccount": OTHER,
                "toUserAccount": WALLET,
                "mint": USDC_MINT,
                "tokenAmount": 4012.0,
            },
            {
                "fromUserAccount": WALLET,
                "toUserAccount": OTHER,
                "mint": pump,
                "tokenAmount": 14276161.0,
            },
        ],
    }
    parsed = parse_helius_swap(tx, {WALLET})
    assert parsed is not None
    assert parsed["side"] == "sell"
    assert parsed["mint"] == pump


def test_ignores_unwatched_wallet() -> None:
    tx = {
        "type": "SWAP",
        "source": "JUPITER",
        "events": {
            "swap": {
                "nativeInput": {"account": OTHER, "amount": "1000000000"},
                "tokenOutputs": [{"userAccount": OTHER, "mint": TOKEN, "rawTokenAmount": {"tokenAmount": "1"}}],
            }
        },
    }
    assert parse_helius_swap(tx, {WALLET}) is None


def test_skips_stablecoin_buy() -> None:
    tx = {
        "type": "SWAP",
        "source": "JUPITER",
        "signature": "usdc1",
        "feePayer": WALLET,
        "events": {
            "swap": {
                "nativeInput": {"account": WALLET, "amount": "1500000000"},
                "tokenOutputs": [
                    {
                        "userAccount": WALLET,
                        "mint": USDC_MINT,
                        "rawTokenAmount": {"tokenAmount": "225500000", "decimals": 6},
                    }
                ],
            }
        },
    }
    assert parse_helius_swap(tx, {WALLET}) is None


def test_skips_failed_tx() -> None:
    tx = {
        "type": "SWAP",
        "source": "JUPITER",
        "transactionError": {"error": "failed"},
        "events": {
            "swap": {
                "nativeInput": {"account": WALLET, "amount": "1000000000"},
                "tokenOutputs": [{"userAccount": WALLET, "mint": TOKEN, "rawTokenAmount": {"tokenAmount": "1"}}],
            }
        },
    }
    assert parse_helius_swap(tx, {WALLET}) is None
