"""Desk configuration."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

def _repo_root() -> Path:
    p = Path(__file__).resolve()
    if len(p.parents) > 3:
        return p.parents[3]
    return p.parents[1] if len(p.parents) > 1 else Path("/app")


_REPO_ROOT = _repo_root()


class DeskMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    desk_mode: DeskMode = DeskMode.PAPER
    config_dir: Path = Field(
        default_factory=lambda: Path(os.environ.get("CONFIG_DIR", str(_REPO_ROOT / "config")))
    )
    data_dir: Path = Field(
        default_factory=lambda: Path(os.environ.get("DATA_DIR", str(_REPO_ROOT / "data")))
    )
    static_dir: Path | None = Field(
        default_factory=lambda: Path(p) if (p := os.environ.get("STATIC_DIR")) else None
    )
    port: int = 8787
    host: str = "0.0.0.0"

    # Solana core
    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"
    solana_private_key: str | None = None
    helius_api_key: str | None = None
    yellowstone_grpc_endpoint: str = "https://laserstream-mainnet-ewr.helius-rpc.com"
    yellowstone_grpc_x_token: str | None = None

    # Feeds
    cope_api_key: str | None = None
    pumpportal_api_key: str | None = None
    mock_stream: bool = False
    cope_poll_sec: int = 60

    # Scoring / paper
    safety_min_score: int = 65
    entry_min_score: int = 72
    paper_starting_sol: float = 1.0

    # Live trade (PumpPortal local API)
    trade_slippage_pct: float = 12.0
    trade_priority_fee_sol: float = 0.0005
    trade_pool: str = "auto"
    use_jito: bool = False
    jito_block_engine_url: str | None = None
    jito_tip_lamports: int = 100_000

    # Sniper ingest (external hot-path worker → orchestrator)
    sniper_ingest_secret: str | None = None
    orchestrator_url: str = "http://127.0.0.1:8787"

    # Onyx voice (ElevenLabs Maisie)
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str = "QtY3JBOUKEB5xzrRfOKc"
    elevenlabs_model: str = "eleven_flash_v2_5"

    # Deep safety + research
    rugcheck_enabled: bool = True
    openai_api_key: str | None = None
    research_llm_enabled: bool = False
    openai_model: str = "gpt-4o-mini"

    @field_validator("static_dir", mode="before")
    @classmethod
    def _empty_static_none(cls, v: object) -> Path | None:
        if v is None or v == "":
            return None
        return Path(str(v))

    @property
    def effective_rpc_url(self) -> str:
        if self.helius_api_key and "helius" not in self.solana_rpc_url.lower():
            return f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"
        return self.solana_rpc_url

    def integration_flags(self) -> dict[str, bool]:
        return {
            "solana_rpc": bool(self.solana_rpc_url),
            "helius": bool(self.helius_api_key),
            "yellowstone_grpc": bool(
                self.yellowstone_grpc_x_token or self.helius_api_key
            ),
            "live_wallet": bool(self.solana_private_key),
            "cope_fomo": bool(self.cope_api_key),
            "pumpportal_key": bool(self.pumpportal_api_key),
            "pumpportal_stream": True,
            "jito": bool(self.use_jito and self.jito_block_engine_url),
            "sniper_ingest": bool(self.sniper_ingest_secret),
            "mock_stream": self.mock_stream,
            "elevenlabs_tts": bool(self.elevenlabs_api_key),
            "rugcheck": self.rugcheck_enabled,
            "research_llm": bool(self.openai_api_key and self.research_llm_enabled),
        }


settings = Settings()
