"""Helius enhanced webhooks — watch copy wallets for swaps on Jupiter, Raydium, etc."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from orchestrator.models import MintCandidate

log = logging.getLogger(__name__)

SOL_MINT = "So11111111111111111111111111111111111111112"
HELIUS_API = "https://api.helius.xyz/v0/webhooks"

PUMP_VENUES = frozenset(
    {
        "PUMP",
        "PUMPFUN",
        "PUMP_FUN",
        "PUMPSWAP",
        "PUMP.AMM",
        "PUMP_AMM",
    }
)


def is_pump_venue(venue: str | None) -> bool:
    v = str(venue or "").upper().replace(" ", "_").replace(".", "_")
    return v in PUMP_VENUES or v.startswith("PUMP")


def _token_change_amount(change: dict[str, Any]) -> tuple[str, int]:
    mint = str(change.get("mint") or "")
    raw = change.get("rawTokenAmount") or change.get("tokenAmount") or {}
    if isinstance(raw, dict):
        amt = int(str(raw.get("tokenAmount") or raw.get("amount") or "0"))
    else:
        amt = int(raw or 0)
    return mint, amt


def parse_helius_swap(
    tx: dict[str, Any],
    watched: set[str],
) -> dict[str, Any] | None:
    """Parse one enhanced Helius SWAP into a copy buy or sell event."""
    if str(tx.get("type") or "").upper() != "SWAP":
        return None

    venue = str(tx.get("source") or tx.get("programId") or "UNKNOWN")
    signature = str(tx.get("signature") or "")

    for acc in tx.get("accountData") or []:
        account = str(acc.get("account") or "")
        if account not in watched:
            continue
        native_change = int(acc.get("nativeBalanceChange") or 0)
        token_changes = acc.get("tokenBalanceChanges") or []

        bought_mint: str | None = None
        sold_mint: str | None = None
        for tc in token_changes:
            mint, delta = _token_change_amount(tc)
            if not mint or mint == SOL_MINT:
                continue
            if delta > 0:
                bought_mint = mint
            elif delta < 0:
                sold_mint = mint

        sol_spent = max(0.0, -native_change / 1_000_000_000.0)

        if bought_mint and native_change < -2_000_000:
            symbol = _symbol_from_tx(tx, bought_mint)
            return {
                "side": "buy",
                "mint": bought_mint,
                "symbol": symbol,
                "trader": account,
                "trader_sol": round(sol_spent, 4) if sol_spent > 0 else None,
                "venue": venue,
                "signature": signature,
                "via": "helius",
            }

        if sold_mint and native_change > 500_000:
            symbol = _symbol_from_tx(tx, sold_mint)
            return {
                "side": "sell",
                "mint": sold_mint,
                "symbol": symbol,
                "trader": account,
                "venue": venue,
                "signature": signature,
                "via": "helius",
            }

    fee_payer = str(tx.get("feePayer") or "")
    if fee_payer in watched:
        for tt in tx.get("tokenTransfers") or []:
            mint = str(tt.get("mint") or "")
            if not mint or mint == SOL_MINT:
                continue
            to_acct = str(tt.get("toUserAccount") or "")
            from_acct = str(tt.get("fromUserAccount") or "")
            if to_acct == fee_payer:
                amt = float(tt.get("tokenAmount") or 0)
                if amt <= 0:
                    continue
                return {
                    "side": "buy",
                    "mint": mint,
                    "symbol": _symbol_from_tx(tx, mint),
                    "trader": fee_payer,
                    "trader_sol": None,
                    "venue": venue,
                    "signature": signature,
                    "via": "helius",
                }
            if from_acct == fee_payer:
                return {
                    "side": "sell",
                    "mint": mint,
                    "symbol": _symbol_from_tx(tx, mint),
                    "trader": fee_payer,
                    "venue": venue,
                    "signature": signature,
                    "via": "helius",
                }

    return None


def _symbol_from_tx(tx: dict[str, Any], mint: str) -> str:
    for key in ("description",):
        desc = str(tx.get(key) or "")
        if desc and len(desc) <= 32:
            return desc.split()[0][:16].upper()
    return mint[:8].upper()


def swap_to_candidate(event: dict[str, Any], *, copy_boost: int = 25) -> MintCandidate | None:
    if event.get("side") != "buy":
        return None
    mint = str(event.get("mint") or "")
    if len(mint) < 32:
        return None
    return MintCandidate(
        mint=mint,
        symbol=str(event.get("symbol") or mint[:8])[:16],
        name=str(event.get("symbol") or mint[:8])[:64],
        source="copy",
        copy_boost=copy_boost,
        meta={
            "trader": event.get("trader"),
            "trader_sol": event.get("trader_sol"),
            "venue": event.get("venue"),
            "via": event.get("via", "helius"),
            "signature": event.get("signature"),
        },
    )


async def list_webhooks(api_key: str) -> list[dict[str, Any]]:
    url = f"{HELIUS_API}?api-key={api_key}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []


async def sync_wallet_webhook(
    *,
    api_key: str,
    webhook_url: str,
    addresses: list[str],
    auth_header: str,
    data_dir: Path,
) -> dict[str, Any]:
    """Create or update Helius enhanced webhook for SWAP events on copy wallets."""
    state_path = data_dir / "helius_webhook.json"
    stored: dict[str, Any] = {}
    if state_path.exists():
        try:
            stored = json.loads(state_path.read_text())
        except Exception:
            stored = {}

    cleaned = sorted({a.strip() for a in addresses if a and len(a.strip()) >= 32})
    if not cleaned:
        return {"ok": False, "reason": "no_wallets"}

    payload = {
        "webhookURL": webhook_url,
        "webhookType": "enhanced",
        "transactionTypes": ["SWAP"],
        "accountAddresses": cleaned,
        "authHeader": auth_header,
    }

    webhook_id = stored.get("webhook_id")
    base = f"{HELIUS_API}?api-key={api_key}"

    async with httpx.AsyncClient(timeout=45.0) as client:
        if webhook_id:
            resp = await client.put(f"{HELIUS_API}/{webhook_id}?api-key={api_key}", json=payload)
            if resp.status_code in (200, 204):
                stored.update({"webhook_id": webhook_id, "wallets": len(cleaned), "webhookURL": webhook_url})
                state_path.write_text(json.dumps(stored, indent=2))
                return {"ok": True, "action": "updated", "webhook_id": webhook_id, "wallets": len(cleaned)}

        existing = await list_webhooks(api_key)
        for wh in existing:
            if str(wh.get("webhookURL") or "") == webhook_url:
                webhook_id = wh.get("webhookID") or wh.get("webhookId") or wh.get("id")
                if webhook_id:
                    resp = await client.put(f"{HELIUS_API}/{webhook_id}?api-key={api_key}", json=payload)
                    resp.raise_for_status()
                    stored.update({"webhook_id": webhook_id, "wallets": len(cleaned), "webhookURL": webhook_url})
                    state_path.write_text(json.dumps(stored, indent=2))
                    return {"ok": True, "action": "updated", "webhook_id": webhook_id, "wallets": len(cleaned)}

        resp = await client.post(base, json=payload)
        if resp.status_code not in (200, 201):
            detail = resp.text[:240]
            log.warning("helius webhook create failed: %s", detail)
            return {"ok": False, "reason": detail}
        data = resp.json()
        webhook_id = data.get("webhookID") or data.get("webhookId") or data.get("id")
        stored.update({"webhook_id": webhook_id, "wallets": len(cleaned), "webhookURL": webhook_url})
        state_path.write_text(json.dumps(stored, indent=2))
        return {"ok": True, "action": "created", "webhook_id": webhook_id, "wallets": len(cleaned)}
