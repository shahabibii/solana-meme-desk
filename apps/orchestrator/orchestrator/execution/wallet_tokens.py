"""On-chain SPL token discovery and dead-bag disposal."""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.transaction import Transaction

from orchestrator.feeds.copy_filters import COPY_SKIP_MINTS, is_copyable_mint

TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
TOKEN_2022_PROGRAM = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")


@dataclass
class WalletToken:
    mint: str
    account: str
    amount_raw: int
    ui_amount: float
    decimals: int


async def list_wallet_tokens(rpc_url: str, owner: str) -> list[WalletToken]:
    out: list[WalletToken] = []
    seen_accounts: set[str] = set()
    for program in (str(TOKEN_PROGRAM), str(TOKEN_2022_PROGRAM)):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                owner,
                {"programId": program},
                {"encoding": "jsonParsed"},
            ],
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(rpc_url, json=payload)
            try:
                data = resp.json()
            except Exception:
                continue
        for item in (data.get("result") or {}).get("value") or []:
            pubkey = str(item.get("pubkey") or "")
            if pubkey in seen_accounts:
                continue
            seen_accounts.add(pubkey)
            parsed = ((item.get("account") or {}).get("data") or {}).get("parsed", {})
            info = parsed.get("info") or {}
            mint = str(info.get("mint") or "")
            if not is_copyable_mint(mint):
                continue
            token_amount = info.get("tokenAmount") or {}
            amount_raw = int(str(token_amount.get("amount") or "0"))
            ui_amount = float(token_amount.get("uiAmount") or 0)
            if amount_raw <= 0:
                continue
            out.append(
                WalletToken(
                    mint=mint,
                    account=pubkey,
                    amount_raw=amount_raw,
                    ui_amount=ui_amount,
                    decimals=int(token_amount.get("decimals") or 0),
                )
            )
    return out


async def estimate_entry_sol_for_mint(
    rpc_url: str, owner: str, mint: str, *, default: float = 0.07
) -> tuple[float, datetime | None]:
    """Sum SOL spent on buys for a mint from recent wallet signatures."""
    spent = 0.0
    first_ts: datetime | None = None
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [owner, {"limit": 60}],
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            sig_resp = await client.post(rpc_url, json=payload)
            sig_data = sig_resp.json()
            sigs = [row["signature"] for row in (sig_data.get("result") or [])]
            for sig in reversed(sigs):
                tx_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTransaction",
                    "params": [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
                }
                tx_resp = await client.post(rpc_url, json=tx_payload)
                try:
                    tx = tx_resp.json().get("result")
                except Exception:
                    continue
                if not tx or (tx.get("meta") or {}).get("err"):
                    continue
                meta = tx["meta"]
                keys = [
                    a.get("pubkey") if isinstance(a, dict) else str(a)
                    for a in tx["transaction"]["message"]["accountKeys"]
                ]
                if owner not in keys:
                    continue
                idx = keys.index(owner)
                delta = (meta["postBalances"][idx] - meta["preBalances"][idx]) / 1e9
                pre = {
                    t["mint"]: float((t.get("uiTokenAmount") or {}).get("uiAmount") or 0)
                    for t in meta.get("preTokenBalances") or []
                    if t.get("owner") == owner
                }
                post = {
                    t["mint"]: float((t.get("uiTokenAmount") or {}).get("uiAmount") or 0)
                    for t in meta.get("postTokenBalances") or []
                    if t.get("owner") == owner
                }
                mints = set(pre) | set(post)
                got_mint = any(m == mint and post.get(m, 0) > pre.get(m, 0) for m in mints)
                if got_mint and delta < -0.01:
                    spent += abs(delta)
                    bt = tx.get("blockTime")
                    if bt:
                        first_ts = first_ts or datetime.fromtimestamp(bt, tz=timezone.utc)
    except Exception:
        return default, first_ts
    if spent <= 0:
        return default, first_ts
    return spent, first_ts


async def burn_and_close_token_account(
    *,
    rpc_url: str,
    keypair: Keypair,
    token_account: str,
    mint: str,
    amount_raw: int,
) -> str:
    """Burn remaining balance and close the token account to reclaim rent."""
    owner = keypair.pubkey()
    acct = Pubkey.from_string(token_account)
    mint_pk = Pubkey.from_string(mint)

    burn_data = bytes([8]) + struct.pack("<Q", amount_raw)
    burn_ix = Instruction(
        TOKEN_PROGRAM,
        [
            AccountMeta(acct, False, True),
            AccountMeta(mint_pk, False, False),
            AccountMeta(owner, True, False),
        ],
        burn_data,
    )
    close_ix = Instruction(
        TOKEN_PROGRAM,
        [
            AccountMeta(acct, False, True),
            AccountMeta(owner, False, True),
            AccountMeta(owner, True, False),
        ],
        bytes([9]),
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        bh_resp = await client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getLatestBlockhash",
                "params": [{"commitment": "finalized"}],
            },
        )
        try:
            bh_data = bh_resp.json()
        except Exception as exc:
            raise RuntimeError(f"blockhash response invalid: {exc}") from exc
        bh = (bh_data.get("result") or {}).get("value", {}).get("blockhash")
        if not bh:
            raise RuntimeError("Could not fetch blockhash")
        msg = Message.new_with_blockhash([burn_ix, close_ix], owner, Hash.from_string(bh))
        tx = Transaction.new_unsigned(msg)
        tx.sign([keypair], Hash.from_string(bh))
        encoded = base64.b64encode(bytes(tx)).decode()
        send_resp = await client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [
                    encoded,
                    {"encoding": "base64", "skipPreflight": False, "maxRetries": 3},
                ],
            },
        )
        send_data = send_resp.json()
        if "error" in send_data:
            raise RuntimeError(send_data["error"].get("message", str(send_data["error"])))
        return str(send_data["result"])
