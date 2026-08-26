//! Yellowstone gRPC sniper — Pump.fun create txs → orchestrator ingest API.
//!
//! Requires a Dragon's Mouth compatible endpoint (Helius, Triton, QuickNode, etc.)

use std::collections::{HashMap, HashSet};
use std::env;
use std::time::Duration;

use anyhow::{Context, Result};
use futures::StreamExt;
use log::{info, warn};
use reqwest::Client;
use serde::Serialize;
use yellowstone_grpc_client::GeyserGrpcClient;
use yellowstone_grpc_proto::geyser::subscribe_update::UpdateOneof;
use yellowstone_grpc_proto::geyser::{
    CommitmentLevel, SubscribeRequest, SubscribeRequestFilterTransactions,
};
use yellowstone_grpc_proto::prelude::SubscribeRequestPing;

const PUMP_PROGRAM: &str = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P";
/// Anchor discriminator for Pump.fun `global:create`
const CREATE_DISCRIMINATOR: [u8; 8] = [24, 30, 200, 40, 5, 28, 7, 119];

#[derive(Serialize)]
struct IngestBody<'a> {
    mint: &'a str,
    symbol: &'a str,
    name: &'a str,
    source: &'a str,
    copy_boost: i32,
}

struct Config {
    grpc_endpoint: String,
    grpc_token: String,
    orchestrator_url: String,
    ingest_secret: Option<String>,
}

impl Config {
    fn from_env() -> Result<Self> {
        let grpc_endpoint = env::var("YELLOWSTONE_GRPC_ENDPOINT").unwrap_or_else(|_| {
            "https://grpc.helius-rpc.com".to_string()
        });
        let grpc_token = env::var("YELLOWSTONE_GRPC_X_TOKEN")
            .or_else(|_| env::var("HELIUS_API_KEY"))
            .context("Set YELLOWSTONE_GRPC_X_TOKEN or HELIUS_API_KEY")?;
        let orchestrator_url = env::var("ORCHESTRATOR_URL")
            .unwrap_or_else(|_| "http://127.0.0.1:8787".to_string())
            .trim_end_matches('/')
            .to_string();
        let ingest_secret = env::var("SNIPER_INGEST_SECRET").ok();
        Ok(Self {
            grpc_endpoint,
            grpc_token,
            orchestrator_url,
            ingest_secret,
        })
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();
    let cfg = Config::from_env()?;
    info!(
        "meme-sniper-rs → {} via {}",
        cfg.orchestrator_url, cfg.grpc_endpoint
    );

    loop {
        if let Err(e) = run_stream(&cfg).await {
            warn!("stream error: {e:#}; reconnecting in 5s");
            tokio::time::sleep(Duration::from_secs(5)).await;
        }
    }
}

async fn run_stream(cfg: &Config) -> Result<()> {
    let mut client = GeyserGrpcClient::build_from_shared(cfg.grpc_endpoint.clone())?
        .x_token(Some(cfg.grpc_token.clone()))?
        .connect_timeout(Duration::from_secs(20))
        .timeout(Duration::from_secs(60))
        .connect()
        .await
        .context("gRPC connect failed")?;

    let mut transactions = HashMap::new();
    transactions.insert(
        "pump_creates".to_string(),
        SubscribeRequestFilterTransactions {
            vote: Some(false),
            failed: Some(false),
            account_include: vec![PUMP_PROGRAM.to_string()],
            ..Default::default()
        },
    );

    let request = SubscribeRequest {
        transactions,
        commitment: Some(CommitmentLevel::Processed as i32),
        ..Default::default()
    };

    let (mut subscribe_tx, mut stream) = client.subscribe().await?;
    subscribe_tx.send(request).await?;

    let http = Client::builder().timeout(Duration::from_secs(10)).build()?;
    let mut seen: HashSet<String> = HashSet::new();

    while let Some(result) = stream.next().await {
        let msg = result?;
        if let Some(UpdateOneof::Ping(_)) = &msg.update_oneof {
            subscribe_tx
                .send(SubscribeRequest {
                    ping: Some(SubscribeRequestPing { id: 1 }),
                    ..Default::default()
                })
                .await
                .ok();
            continue;
        }

        let Some(UpdateOneof::Transaction(tx_wrap)) = msg.update_oneof else {
            continue;
        };
        let Some(tx_info) = tx_wrap.transaction else {
            continue;
        };
        let Some(tx) = tx_info.transaction else {
            continue;
        };
        let Some(message) = tx.message else {
            continue;
        };

        let account_keys: Vec<String> = message
            .account_keys
            .iter()
            .map(|k| bs58::encode(k).into_string())
            .collect();

        for ix in &message.instructions {
            let prog_idx = ix.program_id_index as usize;
            let Some(prog_key) = account_keys.get(prog_idx) else {
                continue;
            };
            if prog_key != PUMP_PROGRAM {
                continue;
            }
            if ix.data.len() < 8 || ix.data[..8] != CREATE_DISCRIMINATOR {
                continue;
            }
            let Some(&mint_idx) = ix.accounts.first() else {
                continue;
            };
            let Some(mint) = account_keys.get(mint_idx as usize) else {
                continue;
            };
            if mint.len() < 32 || seen.contains(mint) {
                continue;
            }
            seen.insert(mint.clone());
            if seen.len() > 50_000 {
                seen.clear();
            }

            let symbol = "NEW";
            if let Err(e) = post_ingest(&http, cfg, mint, symbol).await {
                warn!("ingest {mint}: {e:#}");
            } else {
                info!("ingested create mint={mint}");
            }
        }
    }

    Ok(())
}

async fn post_ingest(http: &Client, cfg: &Config, mint: &str, symbol: &str) -> Result<()> {
    let body = IngestBody {
        mint,
        symbol,
        name: symbol,
        source: "yellowstone",
        copy_boost: 8,
    };
    let url = format!("{}/api/ingest/candidate", cfg.orchestrator_url);
    let mut req = http.post(&url).json(&body);
    if let Some(secret) = &cfg.ingest_secret {
        req = req.header("X-Sniper-Secret", secret);
    }
    let resp = req.send().await?;
    if !resp.status().is_success() {
        anyhow::bail!("HTTP {} {}", resp.status(), resp.text().await.unwrap_or_default());
    }
    Ok(())
}
