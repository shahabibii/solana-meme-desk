# Solana Meme Desk — Onyx + Orchestrator + Rust sniper
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY apps/onyx/package.json apps/onyx/package-lock.json ./
RUN npm ci
COPY apps/onyx/ ./
RUN npm run build

FROM rust:1-bookworm AS sniper
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends protobuf-compiler && rm -rf /var/lib/apt/lists/*
COPY apps/sniper-rs/Cargo.toml apps/sniper-rs/Cargo.lock* ./
COPY apps/sniper-rs/src ./src
RUN cargo build --release

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8787 \
    DATA_DIR=/data \
    CONFIG_DIR=/config \
    STATIC_DIR=/app/static

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY apps/orchestrator/pyproject.toml apps/orchestrator/README.md ./
COPY apps/orchestrator/orchestrator ./orchestrator
RUN pip install --no-cache-dir -e ".[backtest]"

COPY config /config
COPY --from=web /web/dist /app/static
COPY --from=sniper /build/target/release/meme-sniper-rs /app/meme-sniper-rs

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/health')"

CMD ["sh", "-c", "uvicorn orchestrator.main:app --host 0.0.0.0 --port ${PORT:-8787}"]
