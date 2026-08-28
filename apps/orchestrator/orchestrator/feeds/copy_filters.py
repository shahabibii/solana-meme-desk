"""Mints to ignore when mirroring wallet trades (SOL/stables, not meme targets)."""

from __future__ import annotations

# Native + wrapped SOL, major stables — swapping these is not a meme copy target.
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
PYUSD_MINT = "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo"

COPY_SKIP_MINTS = frozenset(
    {
        SOL_MINT,
        USDC_MINT,
        USDT_MINT,
        PYUSD_MINT,
    }
)


def is_copyable_mint(mint: str | None) -> bool:
    """True if mint is a plausible meme/token copy target (not SOL or a stable)."""
    if not mint or len(mint) < 32:
        return False
    return mint not in COPY_SKIP_MINTS
