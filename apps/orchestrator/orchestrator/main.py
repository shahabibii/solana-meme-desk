"""FastAPI app — REST + WebSocket for Onyx."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from orchestrator.agents.backtest import run_backtest
from orchestrator.agents.scorer import run_learner
from orchestrator.config import DeskMode, settings
from orchestrator.desk import DeskRuntime, load_risk_limits, start_desk
from orchestrator.execution.live import LiveExecutor
from orchestrator.execution.paper import PaperBook
from orchestrator.journal.store import JournalStore
from orchestrator.ws.events import mode_changed, status_snapshot

journal = JournalStore(settings.data_dir / "desk.db")
paper_book = PaperBook.new(settings.paper_starting_sol, load_risk_limits(settings.config_dir))
live_exec = LiveExecutor(settings)
_desk_mode = settings.desk_mode
_ws_clients: set[WebSocket] = set()
_tasks: list[asyncio.Task] = []
_running = True
_desk: DeskRuntime | None = None


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
    global _tasks, _running, _desk
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    journal.record_equity(paper_book.equity_sol)
    _desk, _tasks = await start_desk(
        settings, get_mode, paper_book, live_exec, journal, _broadcast, lambda: _running
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


def _integrations() -> dict[str, Any]:
    flags = settings.integration_flags()
    return {
        "integrations": {
            "solana_rpc": {
                "active": flags["solana_rpc"],
                "hint": settings.effective_rpc_url.split("?")[0][:48],
            },
            "helius": {"active": flags["helius"]},
            "live_wallet": {
                "active": flags["live_wallet"],
                "ready": live_exec.ready,
                "pubkey": live_exec.public_key[:8] + "…" if live_exec.public_key else None,
            },
            "cope_fomo": {"active": flags["cope_fomo"]},
            "pumpportal_key": {"active": flags["pumpportal_key"]},
            "pumpportal_stream": {"active": True},
            "jito": {
                "active": flags["jito"],
                "url": (settings.jito_block_engine_url or "")[:40] or None,
            },
            "sniper_ingest": {"active": flags["sniper_ingest"]},
            "mock_stream": {"active": flags["mock_stream"]},
        },
        "live_requires": ["SOLANA_PRIVATE_KEY", "SOLANA_RPC_URL or HELIUS_API_KEY"],
        "optional_boosters": [
            "COPE_API_KEY",
            "PUMPPORTAL_API_KEY",
            "HELIUS_API_KEY",
            "JITO_BLOCK_ENGINE_URL + USE_JITO=true",
            "SNIPER_INGEST_SECRET",
        ],
    }


def _desk_status() -> dict[str, Any]:
    return {
        "mode": _desk_mode.value,
        "live_ready": live_exec.ready,
        "mock_stream": settings.mock_stream,
        "pumpportal": True,
        "agents": [
            "scout",
            "safety",
            "copy",
            "research",
            "scorer",
            "executor",
            "learner",
        ],
        "wallet": paper_book.to_dict(),
        "stats": journal.stats(),
        "fomo_enabled": bool(settings.cope_api_key),
        "learner_weights": journal.get_weights(),
        "ws_clients": len(_ws_clients),
        "integrations": _integrations()["integrations"],
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
def status() -> dict[str, Any]:
    return _desk_status()


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
    return {"accepted": ok, "mint": body.mint}


@app.post("/api/chat")
def chat(body: ChatBody) -> dict[str, str]:
    lower = body.text.lower()
    st = _desk_status()
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
    if "live" in lower:
        if live_exec.ready:
            return {"reply": "Live executor ready. Toggle Live in the header with confirmation."}
        return {"reply": "Set SOLANA_PRIVATE_KEY and SOLANA_RPC_URL (or HELIUS_API_KEY) in .env."}
    if "paper" in lower:
        return {"reply": "Paper mode simulates bonding-curve fills with full safety and journal."}
    if "block" in lower:
        return {"reply": f"Safety blocks so far: {st['stats']['blocks']}."}
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
    return {"reply": "Ask: status, keys, live, paper, blocks, backtest."}


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
    await _broadcast(mode_changed(_desk_mode.value))
    await _broadcast(status_snapshot({"mode": _desk_mode.value, "wallet": paper_book.to_dict()}))
    return {"mode": _desk_mode.value, "live_ready": live_exec.ready}


@app.websocket("/ws/onyx")
async def onyx_ws(ws: WebSocket) -> None:
    await ws.accept()
    _ws_clients.add(ws)
    await ws.send_json(status_snapshot(_desk_status()).to_wire())
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
