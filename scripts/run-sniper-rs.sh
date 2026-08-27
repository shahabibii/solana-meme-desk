#!/bin/sh
# Fly sniper process — idle when LaserStream plan unavailable.
set -e
ORCH="${ORCHESTRATOR_URL:-http://127.0.0.1:8787}"
WORKER="${SNIPER_WORKER_NAME:-yellowstone}"

post_hb() {
  status="$1"
  detail="$2"
  curl -sf -X POST "${ORCH}/api/sniper/heartbeat" \
    -H "Content-Type: application/json" \
    ${SNIPER_INGEST_SECRET:+-H "X-Sniper-Secret: $SNIPER_INGEST_SECRET"} \
    -d "{\"worker\":\"$WORKER\",\"status\":\"$status\",\"detail\":\"$detail\"}" \
    >/dev/null 2>&1 || true
}

if [ "${SNIPER_RS_ENABLED:-true}" = "false" ]; then
  echo "meme-sniper-rs disabled (SNIPER_RS_ENABLED=false) — PumpPortal backup active"
  post_hb "disabled" "LaserStream sniper off; enable when Helius plan supports gRPC"
  while true; do sleep 3600; post_hb "disabled" "idle"; done
fi

exec /app/meme-sniper-rs
