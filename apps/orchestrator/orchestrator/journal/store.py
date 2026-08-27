"""SQLite trade journal + equity curve."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JournalStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._init()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    mint TEXT NOT NULL,
                    symbol TEXT,
                    side TEXT NOT NULL,
                    sol REAL,
                    pnl_pct REAL,
                    mode TEXT,
                    source TEXT,
                    safety_score INTEGER,
                    detail TEXT
                );
                CREATE TABLE IF NOT EXISTS equity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    equity_sol REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    mint TEXT,
                    reasons TEXT
                );
                CREATE TABLE IF NOT EXISTS learner_weights (
                    key TEXT PRIMARY KEY,
                    weight REAL NOT NULL,
                    updated_ts TEXT
                );
                """
            )

    def record_trade(
        self,
        *,
        mint: str,
        symbol: str,
        side: str,
        sol: float,
        pnl_pct: float | None,
        mode: str,
        source: str,
        safety_score: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                """INSERT INTO trades (ts,mint,symbol,side,sol,pnl_pct,mode,source,safety_score,detail)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    ts,
                    mint,
                    symbol,
                    side,
                    sol,
                    pnl_pct,
                    mode,
                    source,
                    safety_score,
                    json.dumps(detail or {}),
                ),
            )

    def record_block(self, mint: str, reasons: list[str]) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO blocks (ts,mint,reasons) VALUES (?,?,?)",
                (ts, mint, json.dumps(reasons)),
            )

    def record_equity(self, equity_sol: float) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO equity (ts,equity_sol) VALUES (?,?)",
                (ts, equity_sol),
            )

    def stats(self) -> dict[str, Any]:
        with self._conn() as c:
            sells = c.execute(
                "SELECT pnl_pct FROM trades WHERE side='sell' AND pnl_pct IS NOT NULL"
            ).fetchall()
            total = c.execute("SELECT COUNT(*) AS n FROM trades").fetchone()["n"]
            blocks = c.execute("SELECT COUNT(*) AS n FROM blocks").fetchone()["n"]
        pnls = [float(r["pnl_pct"]) for r in sells]
        wins = [p for p in pnls if p > 0]
        return {
            "total_trades": total,
            "closed_trades": len(pnls),
            "blocks": blocks,
            "win_rate": (len(wins) / len(pnls)) if pnls else None,
            "avg_pnl_pct": (sum(pnls) / len(pnls)) if pnls else None,
            "total_pnl_pct": sum(pnls) if pnls else 0.0,
        }

    def equity_curve(self, limit: int = 120) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT ts, equity_sol FROM equity ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"ts": r["ts"], "equity_sol": r["equity_sol"]} for r in reversed(rows)]

    def recent_trades(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_weights(self) -> dict[str, float]:
        with self._conn() as c:
            rows = c.execute("SELECT key, weight FROM learner_weights").fetchall()
        defaults = {"pump": 1.0, "fomo": 1.0, "convergence": 1.2, "copy": 1.15, "safety": 1.0}
        for r in rows:
            defaults[r["key"]] = float(r["weight"])
        return defaults

    def set_weight(self, key: str, weight: float) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                """INSERT INTO learner_weights (key, weight, updated_ts) VALUES (?,?,?)
                   ON CONFLICT(key) DO UPDATE SET weight=excluded.weight, updated_ts=excluded.updated_ts""",
                (key, weight, ts),
            )
