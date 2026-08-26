"""Desk configuration."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeskMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    desk_mode: DeskMode = DeskMode.PAPER
    config_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3] / "config")
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3] / "data")
    solana_rpc_url: str = "https://api.mainnet-beta.solana.com"
    solana_private_key: str | None = None
    cope_api_key: str | None = None
    pumpportal_api_key: str | None = None
    mock_stream: bool = False
    safety_min_score: int = 65
    entry_min_score: int = 72
    cope_poll_sec: int = 60

    paper_starting_sol: float = 1.0


settings = Settings()
