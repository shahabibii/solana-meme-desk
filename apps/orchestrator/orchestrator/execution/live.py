"""Live execution seam — wired but gated until keys + RPC configured."""

from __future__ import annotations

from orchestrator.config import Settings


class LiveExecutor:
    """Placeholder for PumpPortal local API / Jupiter swaps."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def ready(self) -> bool:
        return bool(self._settings.solana_private_key and self._settings.solana_rpc_url)

    async def buy(self, mint: str, sol: float) -> dict:
        if not self.ready:
            raise RuntimeError("Live mode not configured — set SOLANA_PRIVATE_KEY and RPC")
        # Phase 2: PumpPortal trade-local + sign + send
        return {"status": "pending_implementation", "mint": mint, "sol": sol}

    async def sell(self, mint: str, fraction: float = 1.0) -> dict:
        if not self.ready:
            raise RuntimeError("Live mode not configured")
        return {"status": "pending_implementation", "mint": mint, "fraction": fraction}
