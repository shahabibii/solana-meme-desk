"""Live execution — PumpPortal trade-local + sign + RPC/Jito send."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

from orchestrator.config import Settings

log = logging.getLogger(__name__)

TRADE_LOCAL = "https://pumpportal.fun/api/trade-local"
LIGHTNING = "https://pumpportal.fun/api/trade"


class LiveExecutor:
    """PumpPortal local (non-custodial) or lightning (API key) execution."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._keypair: Keypair | None = None
        if settings.solana_private_key:
            try:
                self._keypair = Keypair.from_base58_string(settings.solana_private_key.strip())
            except Exception as exc:
                log.warning("Invalid SOLANA_PRIVATE_KEY: %s", exc)

    @property
    def ready(self) -> bool:
        return self._keypair is not None and bool(self._settings.effective_rpc_url)

    @property
    def public_key(self) -> str | None:
        if not self._keypair:
            return None
        return str(self._keypair.pubkey())

    async def buy(self, mint: str, sol: float) -> dict[str, Any]:
        return await self._trade("buy", mint, sol, denominated_in_sol=True)

    async def sell(self, mint: str, fraction: float = 1.0) -> dict[str, Any]:
        amount: float | str = f"{int(round(fraction * 100))}%"
        return await self._trade("sell", mint, amount, denominated_in_sol=False)

    async def _trade(
        self,
        action: str,
        mint: str,
        amount: float | str,
        *,
        denominated_in_sol: bool,
    ) -> dict[str, Any]:
        if not self.ready or not self._keypair:
            raise RuntimeError("Live mode not configured — set SOLANA_PRIVATE_KEY and RPC")

        if self._settings.pumpportal_api_key and not self._settings.solana_private_key:
            return await self._lightning_trade(action, mint, amount, denominated_in_sol)

        body = {
            "publicKey": self.public_key,
            "action": action,
            "mint": mint,
            "amount": amount,
            "denominatedInSol": "true" if denominated_in_sol else "false",
            "slippage": self._settings.trade_slippage_pct,
            "priorityFee": self._settings.trade_priority_fee_sol,
            "pool": self._settings.trade_pool,
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(TRADE_LOCAL, json=body)
            if resp.status_code != 200:
                detail = resp.text[:240]
                raise RuntimeError(f"PumpPortal trade-local failed ({resp.status_code}): {detail}")

            raw = resp.content
            if not raw:
                raise RuntimeError("PumpPortal returned empty transaction")

            tx = VersionedTransaction.from_bytes(raw)
            signed = VersionedTransaction(tx.message, [self._keypair])
            sig = await self._send_transaction(client, bytes(signed))

        return {
            "status": "submitted",
            "signature": sig,
            "mint": mint,
            "action": action,
            "amount": amount,
            "mode": "local",
        }

    async def _lightning_trade(
        self,
        action: str,
        mint: str,
        amount: float | str,
        denominated_in_sol: bool,
    ) -> dict[str, Any]:
        """Custodial PumpPortal lightning wallet when only API key is set."""
        key = self._settings.pumpportal_api_key
        if not key:
            raise RuntimeError("Lightning trade requires PUMPPORTAL_API_KEY")

        params = {
            "action": action,
            "mint": mint,
            "amount": amount,
            "denominatedInSol": "true" if denominated_in_sol else "false",
            "slippage": self._settings.trade_slippage_pct,
            "priorityFee": self._settings.trade_priority_fee_sol,
            "pool": self._settings.trade_pool,
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.get(
                LIGHTNING,
                params=params,
                headers={"Authorization": f"Bearer {key}"},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"PumpPortal lightning failed ({resp.status_code}): {resp.text[:200]}")
            data = resp.json()
        return {
            "status": "submitted",
            "signature": data.get("signature") or data.get("tx"),
            "mint": mint,
            "action": action,
            "amount": amount,
            "mode": "lightning",
        }

    async def _send_transaction(self, client: httpx.AsyncClient, signed_bytes: bytes) -> str:
        encoded = base64.b64encode(signed_bytes).decode()
        rpc = self._settings.effective_rpc_url

        if self._settings.use_jito and self._settings.jito_block_engine_url:
            sig = await self._send_jito_bundle(client, encoded)
            if sig:
                return sig

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded,
                {"encoding": "base64", "skipPreflight": False, "maxRetries": 3},
            ],
        }
        resp = await client.post(rpc, json=payload)
        data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        return str(data["result"])

    async def _send_jito_bundle(self, client: httpx.AsyncClient, tx_b64: str) -> str | None:
        url = self._settings.jito_block_engine_url
        if not url:
            return None
        bundle_url = url.rstrip("/") + "/api/v1/bundles"
        body = {"jsonrpc": "2.0", "id": 1, "method": "sendBundle", "params": [[tx_b64]]}
        try:
            resp = await client.post(bundle_url, json=body, timeout=30.0)
            data = resp.json()
            if "result" in data:
                return str(data["result"])
        except Exception as exc:
            log.warning("Jito bundle failed, falling back to RPC: %s", exc)
        return None
