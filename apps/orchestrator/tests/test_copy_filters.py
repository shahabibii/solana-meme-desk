"""Copy mint filters — skip SOL and stables."""

from orchestrator.feeds.copy_filters import USDC_MINT, USDT_MINT, is_copyable_mint

MEME = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"


def test_copyable_meme_mint() -> None:
    assert is_copyable_mint(MEME)


def test_skips_usdc() -> None:
    assert not is_copyable_mint(USDC_MINT)


def test_skips_usdt() -> None:
    assert not is_copyable_mint(USDT_MINT)
