# Deployment guide

## Fly vs Docker Compose — which to use?

| | **Fly.io** | **Docker Compose** |
|---|-----------|-------------------|
| **Purpose** | Production — always-on desk, HTTPS, persistent journal | Local dev / self-hosted VM |
| **Uptime** | Managed, auto-restart | You manage the host |
| **Secrets** | `fly secrets set` (encrypted) | `.env` file on your machine (never commit) |
| **Sniper** | Scale `sniper=1` process on same app | `docker compose up sniper-rs` |
| **Cost** | ~$5–10/mo (512MB + 1GB volume) | Free on your hardware |

**Recommendation:** Use **Docker Compose locally** while tuning agents/paper mode. Use **Fly for production** once you're ready for 24/7 scanning (paper or live).

## What goes where?

### ✅ Commit & push to GitHub

- All source code (`apps/`, `config/`, `Dockerfile`, `fly.toml`)
- `.env.example` (placeholders only)
- Docs, tests, CI workflows

### ❌ Never commit

- `.env` with real keys
- `SOLANA_PRIVATE_KEY`, `HELIUS_API_KEY`, `COPE_API_KEY`, `PUMPPORTAL_API_KEY`
- `SNIPER_INGEST_SECRET` (use a random string, same value in orchestrator + sniper)

### 🔐 Fly secrets (production)

After first deploy:

```bash
fly secrets set \
  SNIPER_INGEST_SECRET="$(openssl rand -hex 24)" \
  HELIUS_API_KEY="your-helius-key" \
  COPE_API_KEY="cope_..." \
  SOLANA_PRIVATE_KEY="base58..."   # only when going LIVE
```

Non-secret config stays in `fly.toml` `[env]` (DESK_MODE=paper, paths, etc.).

## First Fly deploy

```bash
# Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
fly auth login
fly launch --no-deploy    # if app not created yet; use existing fly.toml
fly volumes create desk_data --region iad --size 1
fly deploy
fly scale count web=1 sniper=1   # enable Rust sniper worker
```

Open `https://solana-meme-desk.fly.dev` — Onyx + API on one URL.

## Local production stack

```bash
cp apps/orchestrator/.env.example apps/orchestrator/.env
# Edit .env — set HELIUS_API_KEY + SNIPER_INGEST_SECRET

export HELIUS_API_KEY=...
export SNIPER_INGEST_SECRET=local-dev-secret
docker compose up --build
```

- HUD: http://localhost:8787  
- Sniper-rs forwards creates to orchestrator ingest

## Sniper tiers

1. **meme-sniper-rs** (Yellowstone) — lowest latency; needs Helius (or other gRPC) key  
2. **sniper-py** (PumpPortal WS) — `docker compose --profile fallback up sniper-py`  
3. **Built-in PumpPortal listener** in orchestrator — always on as backup
