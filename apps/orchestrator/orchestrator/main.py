"""FastAPI app — REST + WebSocket for Onyx."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orchestrator.agents.scorer import run_learner
from orchestrator.config import DeskMode, settings
from orchestrator.desk import load_risk_limits, start_desk
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
    global _tasks, _running
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    journal.record_equity(paper_book.equity_sol)
    _tasks = await start_desk(
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
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
def status() -> dict[str, Any]:
    return _desk_status()


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


@app.get("/api/mode")
def get_desk_mode() -> dict[str, Any]:
    return {
        "mode": _desk_mode.value,
        "live_ready": live_exec.ready,
        "live_requires": ["SOLANA_PRIVATE_KEY", "SOLANA_RPC_URL"],
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
