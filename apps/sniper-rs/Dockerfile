FROM rust:1.83-bookworm AS build
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends protobuf-compiler && rm -rf /var/lib/apt/lists/*
COPY apps/sniper-rs/Cargo.toml apps/sniper-rs/Cargo.lock* ./
COPY apps/sniper-rs/src ./src
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /build/target/release/meme-sniper-rs /usr/local/bin/meme-sniper-rs
ENTRYPOINT ["meme-sniper-rs"]
