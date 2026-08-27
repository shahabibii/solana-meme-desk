"""Sniper / feed worker health tracking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class WorkerStatus:
    worker: str
    status: str = "unknown"
    detail: str | None = None
    ingests: int = 0
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        age = time.time() - self.last_seen
        return {
            "worker": self.worker,
            "status": self.status,
            "detail": self.detail,
            "ingests": self.ingests,
            "last_seen_ago_sec": round(age, 1),
            "stale": age > 120,
        }


class SniperHealthStore:
    def __init__(self) -> None:
        self._workers: dict[str, WorkerStatus] = {}

    def heartbeat(
        self,
        worker: str,
        *,
        status: str = "ok",
        detail: str | None = None,
        ingests: int | None = None,
    ) -> None:
        cur = self._workers.get(worker) or WorkerStatus(worker=worker)
        cur.status = status
        cur.detail = detail
        cur.last_seen = time.time()
        if ingests is not None:
            cur.ingests = ingests
        elif status == "ok":
            cur.ingests += 0
        self._workers[worker] = cur

    def touch(self, worker: str, *, status: str = "ok", detail: str | None = None) -> None:
        self.heartbeat(worker, status=status, detail=detail)

    def record_ingest(self, worker: str) -> None:
        cur = self._workers.get(worker) or WorkerStatus(worker=worker)
        cur.ingests += 1
        cur.status = "ok"
        cur.last_seen = time.time()
        self._workers[worker] = cur

    def snapshot(self) -> dict[str, Any]:
        workers = {k: v.to_dict() for k, v in self._workers.items()}
        overall = "ok"
        if not workers:
            overall = "idle"
        elif any(w["status"] in ("error", "disabled") for w in workers.values()):
            overall = "degraded"
        elif any(w.get("stale") for w in workers.values()):
            overall = "stale"
        return {
            "overall": overall,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "workers": workers,
        }
