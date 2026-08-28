"""Helius enhanced webhooks — watch copy wallets for swaps on Jupiter, Raydium, etc."""

from __future__ import annotations

import json
import logging
import re
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


def normalize_webhook_events(body: Any) -> list[dict[str, Any]]:
    """Helius may POST a list or a single enhanced transaction object."""
    if isinstance(body, list):
        return [x for x in body if isinstance(x, dict)]
    if isinstance(body, dict):
        for key in ("transactions", "data", "events"):
            nested = body.get(key)
            if isinstance(nested, list):
                return [x for x in nested if isinstance(x, dict)]
        return [body]
    return []


def _raw_amount(entry: dict[str, Any]) -> int:
    raw = entry.get("rawTokenAmount") or entry.get("tokenAmount") or {}
    if isinstance(raw, dict):
        return int(str(raw.get("tokenAmount") or raw.get("amount") or "0"))
    return int(raw or 0)


def _mint_from_entry(entry: dict[str, Any]) -> str:
    return str(entry.get("mint") or "")


def _user_from_entry(entry: dict[str, Any]) -> str:
    return str(entry.get("userAccount") or entry.get("account") or "")


def _sol_from_lamports(value: Any) -> float | None:
    try:
        lamports = int(str(value or "0"))
    except (TypeError, ValueError):
        return None
    if lamports <= 0:
        return None
    return round(lamports / 1_000_000_000.0, 4)


def _event_base(tx: dict[str, Any]) -> dict[str, Any]:
    return {
        "venue": str(tx.get("source") or tx.get("programId") or "UNKNOWN"),
        "signature": str(tx.get("signature") or ""),
        "via": "helius",
    }


def _parse_events_swap(tx: dict[str, Any], watched: set[str]) -> dict[str, Any] | None:
    swap = (tx.get("events") or {}).get("swap")
    if not isinstance(swap, dict):
        return None

    base = _event_base(tx)

    native_in = swap.get("nativeInput") or {}
    in_acct = str(native_in.get("account") or "")
    if in_acct in watched:
        sol = _sol_from_lamports(native_in.get("amount"))
        for out in swap.get("tokenOutputs") or []:
            mint = _mint_from_entry(out)
            if not mint or mint == SOL_MINT:
                continue
            if _user_from_entry(out) in watched or in_acct in watched:
                return {
                    **base,
                    "side": "buy",
                    "mint": mint,
                    "symbol": _symbol_from_tx(tx, mint),
                    "trader": in_acct,
                    "trader_sol": sol,
                }

    for out in swap.get("tokenOutputs") or []:
        user = _user_from_entry(out)
        mint = _mint_from_entry(out)
        if user not in watched or not mint or mint == SOL_MINT:
            continue
        if _raw_amount(out) <= 0:
            continue
        sol = _sol_from_lamports((native_in or {}).get("amount"))
        if sol is None:
            for nt in tx.get("nativeTransfers") or []:
                if str(nt.get("fromUserAccount") or "") == user:
                    sol = _sol_from_lamports(nt.get("amount"))
                    if sol:
                        break
        return {
            **base,
            "side": "buy",
            "mint": mint,
            "symbol": _symbol_from_tx(tx, mint),
            "trader": user,
            "trader_sol": sol,
        }

    for inp in swap.get("tokenInputs") or []:
        user = _user_from_entry(inp)
        mint = _mint_from_entry(inp)
        if user not in watched or not mint or mint == SOL_MINT:
            continue
        if _raw_amount(inp) <= 0:
            continue
        return {
            **base,
            "side": "sell",
            "mint": mint,
            "symbol": _symbol_from_tx(tx, mint),
            "trader": user,
        }

    native_out = swap.get("nativeOutput") or {}
    out_acct = str(native_out.get("account") or "")
    if out_acct in watched and _sol_from_lamports(native_out.get("amount")):
        for inp in swap.get("tokenInputs") or []:
            mint = _mint_from_entry(inp)
            if mint and mint != SOL_MINT and _user_from_entry(inp) == out_acct:
                return {
                    **base,
                    "side": "sell",
                    "mint": mint,
                    "symbol": _symbol_from_tx(tx, mint),
                    "trader": out_acct,
                }

    return None


def _parse_account_data(tx: dict[str, Any], watched: set[str]) -> dict[str, Any] | None:
    base = _event_base(tx)
    for acc in tx.get("accountData") or []:
        account = str(acc.get("account") or "")
        if account not in watched:
            continue
        native_change = int(acc.get("nativeBalanceChange") or 0)
        token_changes = acc.get("tokenBalanceChanges") or []

        bought_mint: str | None = None
        sold_mint: str | None = None
        for tc in token_changes:
            mint = _mint_from_entry(tc)
            if not mint or mint == SOL_MINT:
                continue
            amt = _raw_amount(tc)
            if amt <= 0:
                continue
            # Helius reports positive magnitudes; infer direction from SOL flow.
            if native_change < 0:
                bought_mint = mint
            elif native_change > 0:
                sold_mint = mint
            else:
                bought_mint = mint

        sol_spent = max(0.0, -native_change / 1_000_000_000.0)

        if bought_mint and (native_change < -500_000 or len(token_changes) > 0):
            return {
                **base,
                "side": "buy",
                "mint": bought_mint,
                "symbol": _symbol_from_tx(tx, bought_mint),
                "trader": account,
                "trader_sol": round(sol_spent, 4) if sol_spent > 0 else None,
            }

        if sold_mint and (native_change > 500_000 or len(token_changes) > 0):
            return {
                **base,
                "side": "sell",
                "mint": sold_mint,
                "symbol": _symbol_from_tx(tx, sold_mint),
                "trader": account,
            }

    return None


def _parse_token_transfers(tx: dict[str, Any], watched: set[str]) -> dict[str, Any] | None:
    base = _event_base(tx)
    sol_spent: dict[str, float] = {}
    for nt in tx.get("nativeTransfers") or []:
        sender = str(nt.get("fromUserAccount") or "")
        if sender in watched:
            sol = _sol_from_lamports(nt.get("amount"))
            if sol:
                sol_spent[sender] = max(sol_spent.get(sender, 0.0), sol)

    for tt in tx.get("tokenTransfers") or []:
        mint = str(tt.get("mint") or "")
        if not mint or mint == SOL_MINT:
            continue
        to_acct = str(tt.get("toUserAccount") or "")
        from_acct = str(tt.get("fromUserAccount") or "")
        amt = tt.get("tokenAmount")
        try:
            amount = float(amt or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            continue
        if to_acct in watched:
            return {
                **base,
                "side": "buy",
                "mint": mint,
                "symbol": _symbol_from_tx(tx, mint),
                "trader": to_acct,
                "trader_sol": sol_spent.get(to_acct),
            }
        if from_acct in watched:
            return {
                **base,
                "side": "sell",
                "mint": mint,
                "symbol": _symbol_from_tx(tx, mint),
                "trader": from_acct,
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
                return {
                    **base,
                    "side": "buy",
                    "mint": mint,
                    "symbol": _symbol_from_tx(tx, mint),
                    "trader": fee_payer,
                    "trader_sol": sol_spent.get(fee_payer),
                }
            if from_acct == fee_payer:
                return {
                    **base,
                    "side": "sell",
                    "mint": mint,
                    "symbol": _symbol_from_tx(tx, mint),
                    "trader": fee_payer,
                }

    return None


def parse_helius_swap(
    tx: dict[str, Any],
    watched: set[str],
) -> dict[str, Any] | None:
    """Parse one enhanced Helius SWAP into a copy buy or sell event."""
    if str(tx.get("type") or "").upper() != "SWAP":
        return None
    if tx.get("transactionError"):
        return None
    if not watched:
        return None

    for parser in (_parse_events_swap, _parse_account_data, _parse_token_transfers):
        parsed = parser(tx, watched)
        if parsed:
            return parsed

    fee_payer = str(tx.get("feePayer") or "")
    if fee_payer in watched:
        log.debug(
            "helius swap unmatched for watched wallet %s sig=%s source=%s",
            fee_payer[:8],
            str(tx.get("signature") or "")[:16],
            tx.get("source"),
        )
    return None


def _symbol_from_tx(tx: dict[str, Any], mint: str) -> str:
    desc = str(tx.get("description") or "")
    if desc:
        # "WALLET swapped 1.5 SOL for 225.5 BONK on JUPITER"
        m = re.search(r"for\s+[\d.]+\s+(\S+)", desc, re.IGNORECASE)
        if m:
            return m.group(1)[:16].upper()
        first = desc.split()[0]
        if first and len(first) <= 16:
            return first.upper()
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
