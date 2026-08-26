# Yellowstone gRPC sniper (Rust)

Fastest path for Pump.fun **create** detection — streams from a Dragon's Mouth / Yellowstone endpoint (~5ms behind slot) and POSTs mints to the orchestrator ingest API.

## Why Rust + Yellowstone?

| Path | Latency | Role |
|------|---------|------|
| **sniper-rs (Yellowstone)** | ~5–50ms | Primary hot path when you have gRPC |
| **sniper (Python / PumpPortal WS)** | ~100–500ms | Fallback / dev without gRPC |
| **Orchestrator PumpPortal listener** | Same as Python sniper | Backup inside API process |

The prior build skipped Rust because it needed a gRPC provider key, `protoc`, and a separate compile pipeline — not because it isn't the right architecture.

## Env

```bash
export HELIUS_API_KEY=...                          # or YELLOWSTONE_GRPC_X_TOKEN
export YELLOWSTONE_GRPC_ENDPOINT=https://grpc.helius-rpc.com
export ORCHESTRATOR_URL=http://127.0.0.1:8787
export SNIPER_INGEST_SECRET=change-me              # match orchestrator .env
```

## Run locally (Docker — no local Rust needed)

```bash
docker build -f apps/sniper-rs/Dockerfile -t meme-sniper-rs .
docker run --rm -e HELIUS_API_KEY -e ORCHESTRATOR_URL=http://host.docker.internal:8787 meme-sniper-rs
```

## Run with cargo

```bash
cd apps/sniper-rs
cargo run --release
```

Program filter: Pump.fun `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`  
Create discriminator: Anchor `global:create`
