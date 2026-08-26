"""Live executor tests."""

from __future__ import annotations

import httpx
import pytest
import respx
from solders.keypair import Keypair

from orchestrator.config import Settings
from orchestrator.execution.live import LiveExecutor, TRADE_LOCAL


def _b58_keypair() -> tuple[Keypair, str]:
    kp = Keypair()
    secret = str(kp)
    return kp, secret


def test_live_not_ready_without_key() -> None:
    ex = LiveExecutor(Settings(solana_private_key=None))
    assert not ex.ready


def test_live_ready_with_key() -> None:
    _, secret = _b58_keypair()
    ex = LiveExecutor(Settings(solana_private_key=secret, solana_rpc_url="https://rpc.test"))
    assert ex.ready
    assert ex.public_key


@respx.mock
@pytest.mark.asyncio
async def test_live_buy_calls_pumpportal() -> None:
    _, secret = _b58_keypair()
    settings = Settings(solana_private_key=secret, solana_rpc_url="https://rpc.test")
    respx.post(TRADE_LOCAL).mock(return_value=httpx.Response(400, text="bad tx for test"))
    ex = LiveExecutor(settings)
    with pytest.raises(RuntimeError, match="PumpPortal"):
        await ex.buy("7jn4BdR7vmz6Lgece2vieHN6RAyz64P7WhZieQPzpump", 0.01)
