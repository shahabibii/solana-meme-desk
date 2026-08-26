# Solana Meme Desk — Onyx

Autonomous multi-agent desk for **Solana meme coins** (Pump.fun, fomo.family smart money, rug/honeypot gates, sniper + copy execution).

## Stack

| Layer | Path | Role |
|-------|------|------|
| **Onyx** | `apps/onyx` | Jarvis HUD — agents, charts, voice/chat |
| **Orchestrator** | `apps/orchestrator` | Agent pipeline, API, WebSocket, paper/live |
| **Sniper (Rust)** | `apps/sniper-rs` | Yellowstone gRPC — fastest create detection |
| **Sniper (Python)** | `apps/sniper` | PumpPortal WS fallback |

## Quick start (local)

```bash
# Terminal 1 — API + agents
cd apps/orchestrator
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,backtest]"
cp .env.example .env   # add optional keys
uvicorn orchestrator.main:app --reload --port 8787

# Terminal 2 — Onyx HUD
cd apps/onyx
npm install && npm run dev
```

Open http://localhost:5173 — toggle **Paper / Live**, use voice mic in the chat bar.

### Optional: dedicated sniper worker

```bash
cd apps/sniper
pip install -e .
export ORCHESTRATOR_URL=http://127.0.0.1:8787
export SNIPER_INGEST_SECRET=change-me   # match orchestrator .env
python -m sniper.main
```

## Full deck — environment keys

Copy `apps/orchestrator/.env.example` → `.env`:

| Key | Purpose |
|-----|---------|
| `SOLANA_RPC_URL` | RPC for safety + tx send |
| `HELIUS_API_KEY` | Premium RPC (auto URL) |
| `SOLANA_PRIVATE_KEY` | Live signing (PumpPortal trade-local) |
| `COPE_API_KEY` | fomo.family smart money |
| `PUMPPORTAL_API_KEY` | Stream auth + lightning fallback |
| `SNIPER_INGEST_SECRET` | Secure sniper ingest |
| `JITO_BLOCK_ENGINE_URL` + `USE_JITO=true` | Jito bundle send |
| `TRADE_SLIPPAGE_PCT`, `TRADE_PRIORITY_FEE_SOL` | Live trade tuning |

Check active integrations: `GET /api/integrations` or ask Onyx **“keys”**.

## Production (Docker / Fly)

See **[Deployment guide](docs/DEPLOY.md)** — Fly for 24/7 production, Docker Compose for local.

```bash
# Local full stack (orchestrator + Yellowstone sniper)
export HELIUS_API_KEY=...
export SNIPER_INGEST_SECRET=local-dev-secret
docker compose up --build

# Fly production
fly secrets set HELIUS_API_KEY=... SNIPER_INGEST_SECRET=...
fly deploy && fly scale count web=1 sniper=1
```

## Modes

- **Paper** — simulated SOL wallet, bonding-curve fills, full agent + journal loop (default).
- **Live** — PumpPortal trade-local sign + RPC/Jito send; gated on wallet + RPC.

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Onyx UI](docs/ONYX_UI.md)
- [Tooling map](docs/TOOLING.md)
