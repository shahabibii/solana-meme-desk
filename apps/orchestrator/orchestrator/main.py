"""FastAPI app — REST + WebSocket for Onyx."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from orchestrator.alerts import send_alert
from orchestrator.desk_controls import DeskControls
from orchestrator.agents.scorer import run_learner
from orchestrator.config import DeskMode, settings
from orchestrator.config_loaders import load_desk_feed_config
from orchestrator.desk import DeskRuntime, load_risk_limits, start_desk
from orchestrator.execution.live import LiveExecutor
from orchestrator.execution.paper import PaperBook
from orchestrator.journal.store import JournalStore
from orchestrator.sniper_health import SniperHealthStore

log = logging.getLogger(__name__)
from orchestrator.tts.maisie import synthesize_maisie, voice_info
from orchestrator.ws.events import mode_changed, status_snapshot

journal = JournalStore(settings.data_dir / "desk.db")
paper_book = PaperBook.new(settings.paper_starting_sol, load_risk_limits(settings.config_dir))
live_exec = LiveExecutor(settings)
_controls = DeskControls(settings.data_dir, default_mode=settings.desk_mode.value)
_feed_cfg_boot = load_desk_feed_config(settings.config_dir)
_desk_mode = DeskMode(_controls.initial_mode(live_exec.ready))
_ws_clients: set[WebSocket] = set()
_tasks: list[asyncio.Task] = []
_running = True
_desk: DeskRuntime | None = None
_sniper_health = SniperHealthStore()


async def _alert(message: str) -> None:
    if not settings.alert_webhook_url:
        return
    await send_alert(settings.alert_webhook_url, f"**Onyx Desk** · {message}")


async def _broadcast(event) -> None:
    wire = event.to_wire()
    dead: list[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_json(wire)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


def get_mode() -> DeskMode:
    return _desk_mode


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _tasks, _running, _desk, _desk_mode
    _desk_mode = DeskMode(_controls.initial_mode(live_exec.ready))
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    journal.record_equity(paper_book.equity_sol)
    _desk, _tasks = await start_desk(
        settings, get_mode, paper_book, live_exec, journal, _broadcast, lambda: _running,
        on_feed_heartbeat=_sniper_health.touch,
        get_paused=lambda: _controls.paused,
        on_alert=_alert if settings.alert_webhook_url else None,
    )
    yield
    _running = False
    for t in _tasks:
        t.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)


app = FastAPI(title="Onyx Solana Meme Desk", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ModeBody(BaseModel):
    mode: DeskMode
    confirm: bool = False


class IngestBody(BaseModel):
    mint: str
    symbol: str = "SNIP"
    name: str = ""
    source: str = "sniper"
    copy_boost: int = 0


class ChatBody(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class TtsBody(BaseModel):
    text: str = Field(min_length=1, max_length=520)


class HeartbeatBody(BaseModel):
    worker: str = Field(min_length=1, max_length=64)
    status: str = "ok"
    detail: str | None = None
    ingests: int | None = None


class PauseBody(BaseModel):
    paused: bool


class ArmLiveBody(BaseModel):
    confirm: bool = False


class CopyWalletsBody(BaseModel):
    wallets: list[str] = Field(default_factory=list)
    replace: bool = False


class FomoSyncBody(BaseModel):
    fomo_handle: str = Field(min_length=1, max_length=64)


def _setup_checklist() -> dict[str, Any]:
    flags = settings.integration_flags()
    fomo_copy = bool(
        _desk and _desk.feed_cfg.fomo_copy_mode
    ) or _feed_cfg_boot.fomo_copy_mode or settings.fomo_copy_mode
    missing = []
    if not flags["pumpportal_key"]:
        missing.append("PUMPPORTAL_API_KEY — required for wallet copy-trading stream")
    if not flags["elevenlabs_tts"]:
        missing.append("ELEVENLABS_API_KEY — optional Maisie voice")
    if not flags["research_llm"]:
        missing.append("OPENAI_API_KEY + RESEARCH_LLM_ENABLED=true — optional LLM research")
    if not settings.alert_webhook_url:
        missing.append(
            "ALERT_WEBHOOK_URL — optional Slack/Discord alerts on fills/loss cap"
        )
    wallets = len(_desk._copy_wallets) if _desk else 0
    manual = len(_desk.fomo_follows.handles) if _desk else 0
    if wallets == 0:
        if fomo_copy and manual:
            missing.append(
                f"{manual} follows configured — add wallet addresses to start copy-trading"
            )
        elif fomo_copy:
            missing.append("Add copy wallet addresses in config or POST /api/copy/wallets")
        elif not flags["pumpportal_key"]:
            missing.append("copy_wallets.yaml — no mirror wallets yet")
    return {
        "fomo_copy_mode": fomo_copy,
        "ready_for_copy_trading": flags["pumpportal_key"] and wallets > 0,
        "ready_for_live": live_exec.ready,
        "paused": _controls.paused,
        "copy_wallets": wallets,
        "missing": missing,
    }


def _integrations() -> dict[str, Any]:
    flags = settings.integration_flags()
    return {
        "integrations": {
            "solana_rpc": {
                "active": flags["solana_rpc"],
                "hint": settings.effective_rpc_url.split("?")[0][:48],
            },
            "helius": {"active": flags["helius"]},
            "helius_wallets": {"active": flags["helius_wallets"]},
            "jupiter_exec": {"active": flags["jupiter_exec"]},
            "live_wallet": {
                "active": flags["live_wallet"],
                "ready": live_exec.ready,
                "pubkey": live_exec.public_key[:8] + "…" if live_exec.public_key else None,
            },
            "cope_fomo": {"active": flags["cope_fomo"]},
            "pumpportal_key": {"active": flags["pumpportal_key"]},
            "pumpportal_stream": {"active": True},
            "copy_trading": {
                "active": bool(flags["pumpportal_key"]),
                "requires": "PUMPPORTAL_API_KEY + copy wallet addresses",
            },
            "jito": {
                "active": flags["jito"],
                "url": (settings.jito_block_engine_url or "")[:40] or None,
            },
            "sniper_ingest": {"active": flags["sniper_ingest"]},
            "mock_stream": {"active": flags["mock_stream"]},
            "elevenlabs_tts": {
                "active": flags["elevenlabs_tts"],
                "voice": "Maisie",
            },
            "rugcheck": {"active": flags["rugcheck"]},
            "research_llm": {"active": flags["research_llm"]},
        },
        "live_requires": ["SOLANA_PRIVATE_KEY", "SOLANA_RPC_URL or HELIUS_API_KEY"],
        "optional_boosters": [
            "COPE_API_KEY",
            "PUMPPORTAL_API_KEY",
            "HELIUS_API_KEY",
            "ELEVENLABS_API_KEY",
            "JITO_BLOCK_ENGINE_URL + USE_JITO=true",
            "SNIPER_INGEST_SECRET",
        ],
    }


def _desk_status_sync() -> dict[str, Any]:
    wallet = (_desk._wallet_cache if _desk else None) or paper_book.to_dict()
    base = {
        "mode": _desk_mode.value,
        "live_ready": live_exec.ready,
        "mock_stream": settings.mock_stream,
        "pumpportal": bool(_desk.feed_cfg.pump_launch_feed) if _desk else True,
        "pump_launch_feed": _desk.feed_cfg.pump_launch_feed if _desk else True,
        "fomo_copy_mode": (
            _desk.feed_cfg.fomo_copy_mode if _desk else _feed_cfg_boot.fomo_copy_mode
        ),
        "agents": [
            "scout",
            "safety",
            "copy",
            "research",
            "scorer",
            "executor",
            "learner",
        ],
        "wallet": wallet,
        "stats": journal.stats(),
        "fomo_enabled": bool(settings.cope_api_key),
        "learner_weights": journal.get_weights(),
        "ws_clients": len(_ws_clients),
        "integrations": _integrations()["integrations"],
        "setup": _setup_checklist(),
        "paused": _controls.paused,
    }
    if _desk:
        base.update(_desk.status_extra())
    base["sniper_health"] = _sniper_health.snapshot()
    return base


async def _desk_status() -> dict[str, Any]:
    base = _desk_status_sync()
    if _desk:
        base["wallet"] = await _desk.wallet_snapshot(_desk_mode)
        base.update(_desk.status_extra())
        base["fomo_follow_handles"] = list(_desk.fomo_follows.handles)
    base["sniper_health"] = _sniper_health.snapshot()
    return base


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return await _desk_status()


@app.get("/api/integrations")
def integrations() -> dict[str, Any]:
    return _integrations()


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    return journal.stats()


@app.get("/api/equity-curve")
def equity_curve(limit: int = 120) -> dict[str, Any]:
    return {"points": journal.equity_curve(limit)}


@app.get("/api/trades")
def trades(limit: int = 30) -> dict[str, Any]:
    return {"trades": journal.recent_trades(limit)}


@app.post("/api/learner/run")
def learner_run() -> dict[str, Any]:
    weights = run_learner(journal)
    return {"weights": weights}


@app.post("/api/backtest/run")
def backtest_run() -> dict[str, Any]:
    return run_backtest(journal)


@app.post("/api/ingest/candidate")
async def ingest_candidate(
    body: IngestBody,
    x_sniper_secret: str | None = Header(default=None, alias="X-Sniper-Secret"),
) -> dict[str, Any]:
    secret = settings.sniper_ingest_secret
    if secret and x_sniper_secret != secret:
        raise HTTPException(401, detail="Invalid sniper ingest secret")
    if not _desk:
        raise HTTPException(503, detail="Desk not ready")
    ok = await _desk.ingest_candidate(
        mint=body.mint,
        symbol=body.symbol,
        name=body.name,
        source=body.source,
        copy_boost=body.copy_boost,
    )
    if ok and body.source in ("yellowstone", "sniper"):
        _sniper_health.record_ingest(body.source)
    return {"accepted": ok, "mint": body.mint}


@app.post("/api/sniper/heartbeat")
async def sniper_heartbeat(
    body: HeartbeatBody,
    x_sniper_secret: str | None = Header(default=None, alias="X-Sniper-Secret"),
) -> dict[str, str]:
    secret = settings.sniper_ingest_secret
    if secret and x_sniper_secret != secret:
        raise HTTPException(401, detail="Invalid sniper ingest secret")
    _sniper_health.heartbeat(
        body.worker,
        status=body.status,
        detail=body.detail,
        ingests=body.ingests,
    )
    return {"ok": "true"}


@app.get("/api/sniper/health")
def sniper_health() -> dict[str, Any]:
    return _sniper_health.snapshot()


@app.get("/api/setup")
def setup_status() -> dict[str, Any]:
    return _setup_checklist()


@app.post("/api/alerts/test")
async def test_alert(
    x_sniper_secret: str | None = Header(default=None, alias="X-Sniper-Secret"),
) -> dict[str, Any]:
    secret = settings.sniper_ingest_secret
    if secret and x_sniper_secret != secret:
        raise HTTPException(401, detail="Invalid sniper ingest secret")
    if not settings.alert_webhook_url:
        raise HTTPException(400, detail="ALERT_WEBHOOK_URL not configured")
    await _alert("Test alert — Onyx desk notifications are working.")
    return {"ok": True, "message": "Test alert sent"}


@app.post("/api/desk/pause")
async def set_desk_pause(body: PauseBody) -> dict[str, Any]:
    _controls.set_paused(body.paused)
    msg = "Desk paused — no new entries." if body.paused else "Desk resumed."
    if settings.alert_webhook_url:
        await _alert(msg)
    await _broadcast(status_snapshot({"paused": _controls.paused, "setup": _setup_checklist()}))
    return {"paused": _controls.paused, "message": msg}


@app.post("/api/desk/stop")
async def stop_desk() -> dict[str, Any]:
    """Kill switch — pause new entries (persists across restarts)."""
    return await set_desk_pause(PauseBody(paused=True))


@app.post("/api/desk/resume")
async def resume_desk() -> dict[str, Any]:
    return await set_desk_pause(PauseBody(paused=False))


@app.post("/api/desk/arm-live")
async def arm_live_desk(body: ArmLiveBody) -> dict[str, Any]:
    """Arm LIVE, unpause, and persist — safe to close the browser after this."""
    global _desk_mode
    if not body.confirm:
        raise HTTPException(400, detail="Arm LIVE requires confirm=true")
    if not live_exec.ready:
        raise HTTPException(
            400,
            detail="Live not configured — fund wallet and set SOLANA_PRIVATE_KEY",
        )
    _desk_mode = DeskMode.LIVE
    _controls.set_mode(DeskMode.LIVE.value)
    _controls.set_paused(False)
    msg = "LIVE armed — desk running. New entries enabled."
    if settings.alert_webhook_url:
        await _alert(msg)
    await _broadcast(mode_changed(_desk_mode.value))
    wallet = await _desk.wallet_snapshot(_desk_mode) if _desk else paper_book.to_dict()
    snap = status_snapshot(
        {
            "mode": _desk_mode.value,
            "paused": False,
            "wallet": wallet,
            "setup": _setup_checklist(),
        }
    )
    await _broadcast(snap)
    return {
        "mode": _desk_mode.value,
        "paused": False,
        "live_ready": live_exec.ready,
        "message": msg,
    }


@app.post("/api/helius/webhook")
async def helius_webhook(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    """Helius enhanced SWAP webhook — Jupiter, Raydium, Orca, etc."""
    if not _desk:
        raise HTTPException(503, detail="Desk not ready")
    secret = settings.helius_webhook_secret or settings.sniper_ingest_secret
    if secret:
        expected = f"Bearer {secret}"
        if authorization != expected:
            raise HTTPException(401, detail="Invalid webhook authorization")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON body")
    from orchestrator.feeds.helius_wallets import normalize_webhook_events, parse_helius_swap

    events = normalize_webhook_events(body)
    watched = set(_desk._copy_wallets)
    handled = 0
    received = 0
    for raw in events:
        if not isinstance(raw, dict):
            continue
        received += 1
        _sniper_health.record_ingest("helius_wallets")
        parsed = parse_helius_swap(raw, watched)
        if not parsed:
            continue
        handled += 1
        await _desk.on_helius_wallet_trade(parsed, _desk_mode)
    if received and not handled:
        log.debug("helius webhook: received=%s handled=0", received)
    return {"ok": True, "received": received, "handled": handled}


@app.post("/api/helius/sync-webhook")
async def helius_sync_webhook() -> dict[str, Any]:
    if not _desk:
        raise HTTPException(503, detail="Desk not ready")
    result = await _desk.sync_helius_webhook()
    await _broadcast(status_snapshot(await _desk_status()))
    return result


@app.post("/api/desk/fomo-bootstrap")
async def fomo_bootstrap_desk() -> dict[str, Any]:
    """Sync fomo follows, resolve wallets, and seed Cope candidates."""
    if not _desk:
        raise HTTPException(503, detail="Desk not ready")
    result = await _desk.bootstrap_fomo_copy()
    await _broadcast(status_snapshot(await _desk_status()))
    return result


@app.post("/api/desk/reconcile-positions")
async def reconcile_positions() -> dict[str, Any]:
    """Import on-chain SPL holdings into live TP/SL monitor."""
    if not _desk:
        raise HTTPException(503, detail="Desk not ready")
    result = await _desk.reconcile_live_positions()
    await _broadcast(status_snapshot(await _desk_status()))
    return result


@app.post("/api/copy/refresh")
async def refresh_copy_wallets() -> dict[str, Any]:
    if not _desk:
        raise HTTPException(503, detail="Desk not ready")
    wallets = await _desk.refresh_copy_wallets()
    return {"wallets": wallets, "count": len(wallets)}


@app.post("/api/copy/wallets")
async def set_copy_wallets(body: CopyWalletsBody) -> dict[str, Any]:
    """Add or replace manual copy-trading wallets (runtime; persists to copy_wallets.yaml)."""
    if not _desk:
        raise HTTPException(503, detail="Desk not ready")
    cleaned = [w.strip() for w in body.wallets if w and len(w.strip()) >= 32]
    if body.replace:
        _desk.copy_cfg.wallets = cleaned
    else:
        merged = list(_desk.copy_cfg.wallets)
        for w in cleaned:
            if w not in merged:
                merged.append(w)
        _desk.copy_cfg.wallets = merged[: _desk.copy_cfg.max_wallets]

    # Persist on volume so restarts keep the list
    from orchestrator.config_loaders import save_runtime_wallets

    save_runtime_wallets(settings.data_dir, list(_desk.copy_cfg.wallets))

    wallets = await _desk.refresh_copy_wallets()
    return {"wallets": wallets, "count": len(wallets)}


@app.post("/api/fomo/sync")
async def sync_fomo_profile(body: FomoSyncBody) -> dict[str, Any]:
    """Sync fomo.family follows → wallets for PumpPortal copy-trading."""
    if not _desk:
        raise HTTPException(503, detail="Desk not ready")
    if not settings.cope_api_key:
        raise HTTPException(400, detail="COPE_API_KEY not configured")
    handle = body.fomo_handle.strip().lstrip("@")
    # Persist handle for future refreshes (in-memory + env-style via data file)
    settings.fomo_handle = handle
    try:
        (settings.data_dir / "fomo_handle.txt").write_text(handle)
    except Exception:
        pass
    sync = await _desk.cope.sync_fomo(handle)
    follows = await _desk.cope.follows()
    wallets = await _desk.refresh_copy_wallets()
    cope_health = await _desk.cope.health()
    if not follows and not wallets:
        err = (
            _desk.cope.last_error
            or cope_health.get("error")
            or "Cope API returned no follows — api.cope.capital may be down"
        )
        sync = {**(sync if isinstance(sync, dict) else {}), "ok": False, "error": err}
    return {
        "fomo_handle": handle,
        "sync": sync,
        "follows": follows,
        "follow_count": len(follows),
        "wallets": wallets,
        "wallet_count": len(wallets),
        "cope_health": cope_health,
    }


@app.get("/api/voice")
def get_voice() -> dict[str, object]:
    return voice_info()


@app.post("/api/tts")
async def tts(body: TtsBody) -> Response:
    try:
        audio = await synthesize_maisie(body.text.strip())
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/chat")
async def chat(body: ChatBody) -> dict[str, str]:
    lower = body.text.lower()
    st = await _desk_status()
    if "status" in lower or "how" in lower and "desk" in lower:
        w = st["wallet"]
        return {
            "reply": (
                f"{st['mode'].upper()} mode. "
                f"{w['equity_sol']:.3f} SOL equity, {w['open_positions']} open. "
                f"Stream {'live' if len(_ws_clients) else 'idle'}."
            )
        }
    if "integration" in lower or "keys" in lower:
        active = [k for k, v in st["integrations"].items() if v.get("active")]
        return {"reply": f"Active integrations: {', '.join(active) or 'RPC only'}."}
    if "stop" in lower or ("pause" in lower and "unpause" not in lower):
        await set_desk_pause(PauseBody(paused=True))
        return {"reply": "Desk stopped — no new entries. Open positions still monitored."}
    if "resume" in lower or "unpause" in lower or "run" in lower:
        await set_desk_pause(PauseBody(paused=False))
        return {"reply": f"Desk resumed in {st['mode'].upper()} mode."}
    if "arm" in lower and "live" in lower:
        if not live_exec.ready:
            return {"reply": "Wallet not ready — fund your live pubkey first."}
        return {
            "reply": "Use Arm LIVE & Run in the sidebar, or POST /api/desk/arm-live with confirm=true."
        }
    if "live" in lower:
        if live_exec.ready:
            return {
                "reply": "Live ready. Tap Arm LIVE & Run (sidebar) or toggle LIVE in the header."
            }
        return {"reply": "Set SOLANA_PRIVATE_KEY and fund the wallet on-chain."}
    if "paper" in lower:
        return {"reply": "Paper mode simulates bonding-curve fills with full safety and journal."}
    if "block" in lower:
        return {"reply": f"Safety blocks so far: {st['stats']['blocks']}."}
    if "copy" in lower or "fomo" in lower:
        ct = st.get("copy_trading") or {}
        fomo = "ON" if st.get("fomo_copy_mode") else "off"
        return {
            "reply": (
                f"Fomo Copy Mode {fomo}. "
                f"Copy-trading {'on' if ct.get('enabled') else 'off'}. "
                f"Watching {ct.get('wallets', 0)} wallets."
            )
        }
    if "backtest" in lower:
        bt = run_backtest(journal)
        return {
            "reply": (
                f"Backtest ({bt.get('engine')}): {bt.get('round_trips', 0)} round-trips, "
                f"win rate {bt.get('win_rate', 0):.0%}."
                if bt.get("round_trips")
                else "No closed trades yet for backtest."
            )
        }
    return {"reply": "Ask: status, keys, live, paper, blocks, backtest, stop, resume."}


@app.get("/api/mode")
def get_desk_mode() -> dict[str, Any]:
    return {
        "mode": _desk_mode.value,
        "live_ready": live_exec.ready,
        "live_requires": ["SOLANA_PRIVATE_KEY", "SOLANA_RPC_URL or HELIUS_API_KEY"],
    }


@app.patch("/api/mode")
async def set_desk_mode(body: ModeBody) -> dict[str, Any]:
    global _desk_mode
    if body.mode == DeskMode.LIVE:
        if not body.confirm:
            raise HTTPException(400, detail="Switching to LIVE requires confirm=true")
        if not live_exec.ready:
            raise HTTPException(
                400,
                detail="Live not configured — set SOLANA_PRIVATE_KEY in orchestrator .env",
            )
    _desk_mode = body.mode
    _controls.set_mode(_desk_mode.value)
    await _broadcast(mode_changed(_desk_mode.value))
    wallet = await _desk.wallet_snapshot(_desk_mode) if _desk else paper_book.to_dict()
    await _broadcast(status_snapshot({"mode": _desk_mode.value, "wallet": wallet}))
    return {"mode": _desk_mode.value, "live_ready": live_exec.ready}


@app.websocket("/ws/onyx")
async def onyx_ws(ws: WebSocket) -> None:
    await ws.accept()
    _ws_clients.add(ws)
    await ws.send_json(status_snapshot(await _desk_status()).to_wire())
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


def _mount_static() -> None:
    static = settings.static_dir
    if not static or not static.is_dir():
        return
    assets = static / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith(("api/", "ws/")):
            raise HTTPException(404)
        target = static / full_path
        if target.is_file():
            return FileResponse(target)
        index = static / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(404)


_mount_static()
