"""Live execution — PumpPortal trade-local + sign + RPC/Jito send."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

from orchestrator.config import Settings
from orchestrator.execution.jupiter import SOL_MINT, get_token_balance_raw, jupiter_swap
from orchestrator.feeds.helius_wallets import is_pump_venue

log = logging.getLogger(__name__)

TRADE_LOCAL = "https://pumpportal.fun/api/trade-local"
LIGHTNING = "https://pumpportal.fun/api/trade"


def _load_keypair(raw: str) -> Keypair:
    """Accept base58 secret or JSON byte array (Phantom export)."""
    text = raw.strip().strip('"').strip("'")
    if text.startswith("["):
        import json

        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("JSON key must be a byte array")
        return Keypair.from_bytes(bytes(int(x) for x in data))
    return Keypair.from_base58_string(text)


class LiveExecutor:
    """PumpPortal local (non-custodial) or lightning (API key) execution."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._keypair: Keypair | None = None
        if settings.solana_private_key:
            try:
                self._keypair = _load_keypair(settings.solana_private_key)
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

    async def get_balance_sol(self) -> float | None:
        if not self._keypair:
            return None
        rpc = self._settings.effective_rpc_url
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [self.public_key],
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(rpc, json=payload)
                data = resp.json()
                lamports = (data.get("result") or {}).get("value")
                if lamports is None:
                    return None
                return float(lamports) / 1_000_000_000.0
        except Exception:
            return None

    async def buy(self, mint: str, sol: float) -> dict[str, Any]:
        return await self._trade("buy", mint, sol, denominated_in_sol=True)

    async def buy_for_venue(self, mint: str, sol: float, venue: str | None) -> dict[str, Any]:
        if is_pump_venue(venue):
            out = await self.buy(mint, sol)
            out["venue_exec"] = "pumpportal"
            return out
        out = await self.jupiter_buy(mint, sol)
        out["venue_exec"] = "jupiter"
        return out

    async def jupiter_buy(self, mint: str, sol: float) -> dict[str, Any]:
        if not self.ready or not self._keypair:
            raise RuntimeError("Live mode not configured — set SOLANA_PRIVATE_KEY and RPC")
        lamports = int(max(sol, 0.001) * 1_000_000_000)
        slippage_bps = int(self._settings.trade_slippage_pct * 100)
        tip = int(self._settings.trade_priority_fee_sol * 1_000_000_000)
        result = await jupiter_swap(
            keypair=self._keypair,
            rpc_url=self._settings.effective_rpc_url,
            input_mint=SOL_MINT,
            output_mint=mint,
            amount_raw=lamports,
            slippage_bps=slippage_bps,
            priority_fee_lamports=tip,
        )
        result.update({"mint": mint, "action": "buy", "amount": sol, "mode": "jupiter"})
        return result

    async def sell(self, mint: str, fraction: float = 1.0) -> dict[str, Any]:
        amount: float | str = f"{int(round(fraction * 100))}%"
        return await self._trade("sell", mint, amount, denominated_in_sol=False)

    async def sell_for_venue(self, mint: str, fraction: float, venue: str | None) -> dict[str, Any]:
        if is_pump_venue(venue):
            out = await self.sell(mint, fraction)
            out["venue_exec"] = "pumpportal"
            return out
        out = await self.jupiter_sell(mint, fraction)
        out["venue_exec"] = "jupiter"
        return out

    async def jupiter_sell(self, mint: str, fraction: float = 1.0) -> dict[str, Any]:
        if not self.ready or not self._keypair or not self.public_key:
            raise RuntimeError("Live mode not configured — set SOLANA_PRIVATE_KEY and RPC")
        balance = await get_token_balance_raw(self._settings.effective_rpc_url, self.public_key, mint)
        if balance <= 0:
            raise RuntimeError("No token balance to sell")
        amount_raw = max(1, int(balance * max(0.0, min(1.0, fraction))))
        slippage_bps = int(self._settings.trade_slippage_pct * 100)
        tip = int(self._settings.trade_priority_fee_sol * 1_000_000_000)
        result = await jupiter_swap(
            keypair=self._keypair,
            rpc_url=self._settings.effective_rpc_url,
            input_mint=mint,
            output_mint=SOL_MINT,
            amount_raw=amount_raw,
            slippage_bps=slippage_bps,
            priority_fee_lamports=tip,
        )
        result.update(
            {
                "mint": mint,
                "action": "sell",
                "amount": fraction,
                "mode": "jupiter",
            }
        )
        return result

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
