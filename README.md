# Solana Meme Desk — Onyx

Autonomous multi-agent desk for **Solana meme coins** (Pump.fun, fomo.family smart money, rug/honeypot gates, sniper + copy execution).

Legacy equities/options platform: [`../multimodal-trading-platform`](../multimodal-trading-platform) (archived).

## Stack

| Layer | Path | Role |
|-------|------|------|
| **Onyx** | `apps/onyx` | Jarvis HUD — agents at work, charts, voice/chat |
| **Orchestrator** | `apps/orchestrator` | Agent pipeline, API, WebSocket, paper/live toggle |
| **Sniper** | `apps/sniper` | (Phase 2) Yellowstone gRPC / PumpPortal hot path |

## Quick start

```bash
# Terminal 1 — API + mock agent stream
cd apps/orchestrator
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn orchestrator.main:app --reload --port 8787

# Terminal 2 — Onyx HUD
cd apps/onyx
npm install && npm run dev
```

Open http://localhost:5173 — toggle **Paper / Live** in the header (Live arms execution; paper simulates fills).

## Modes

- **Paper** — simulated SOL wallet, bonding-curve fills, full agent + journal loop (default).
- **Live** — real execution path wired but gated; requires `SOLANA_PRIVATE_KEY` + RPC in `.env` (never commit keys).

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Onyx UI](docs/ONYX_UI.md)
