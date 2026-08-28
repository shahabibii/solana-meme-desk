"""Jupiter v6 swap execution for graduated / DEX copy trades."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

log = logging.getLogger(__name__)

SOL_MINT = "So11111111111111111111111111111111111111112"
JUPITER_QUOTE = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP = "https://quote-api.jup.ag/v6/swap"


async def get_token_balance_raw(rpc_url: str, owner: str, mint: str) -> int:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            owner,
            {"mint": mint},
            {"encoding": "jsonParsed"},
        ],
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(rpc_url, json=payload)
        data = resp.json()
        accounts = (data.get("result") or {}).get("value") or []
        total = 0
        for item in accounts:
            info = ((item.get("account") or {}).get("data") or {}).get("parsed", {})
            token_amount = (info.get("info") or {}).get("tokenAmount") or {}
            total += int(str(token_amount.get("amount") or "0"))
        return total


async def jupiter_swap(
    *,
    keypair: Keypair,
    rpc_url: str,
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    slippage_bps: int,
    priority_fee_lamports: int,
) -> dict[str, Any]:
    if amount_raw <= 0:
        raise RuntimeError("Jupiter swap amount must be positive")

    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_raw),
        "slippageBps": str(slippage_bps),
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        quote_resp = await client.get(JUPITER_QUOTE, params=params)
        if quote_resp.status_code != 200:
            raise RuntimeError(f"Jupiter quote failed ({quote_resp.status_code}): {quote_resp.text[:200]}")
        quote = quote_resp.json()

        swap_body = {
            "quoteResponse": quote,
            "userPublicKey": str(keypair.pubkey()),
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": priority_fee_lamports,
        }
        swap_resp = await client.post(JUPITER_SWAP, json=swap_body)
        if swap_resp.status_code != 200:
            raise RuntimeError(f"Jupiter swap failed ({swap_resp.status_code}): {swap_resp.text[:200]}")
        swap_data = swap_resp.json()
        tx_b64 = swap_data.get("swapTransaction")
        if not tx_b64:
            raise RuntimeError("Jupiter returned no swapTransaction")

        tx = VersionedTransaction.from_bytes(base64.b64decode(tx_b64))
        signed = VersionedTransaction(tx.message, [keypair])
        encoded = base64.b64encode(bytes(signed)).decode()

        send_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                encoded,
                {"encoding": "base64", "skipPreflight": False, "maxRetries": 3},
            ],
        }
        send_resp = await client.post(rpc_url, json=send_payload)
        send_data = send_resp.json()
        if "error" in send_data:
            raise RuntimeError(send_data["error"].get("message", str(send_data["error"])))
        signature = str(send_data["result"])

    return {
        "status": "submitted",
        "signature": signature,
        "mode": "jupiter",
        "input_mint": input_mint,
        "output_mint": output_mint,
        "amount_raw": amount_raw,
    }
