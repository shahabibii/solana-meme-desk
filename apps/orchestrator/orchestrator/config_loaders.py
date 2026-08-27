"""Load copy-trading configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CopyConfig:
    enabled: bool = True
    min_trader_sol: float = 0.02
    copy_ratio: float = 0.25
    max_wallets: int = 20
    copy_boost: int = 25
    min_trader_win_rate: float = 0.55
    wallets: list[str] = field(default_factory=list)


def load_copy_config(config_dir: Path) -> CopyConfig:
    path = config_dir / "copy_wallets.yaml"
    if not path.exists():
        return CopyConfig()
    raw = yaml.safe_load(path.read_text()) or {}
    section = raw.get("copy") or {}
    wallets = [str(w) for w in (raw.get("wallets") or []) if w and len(str(w)) >= 32]
    return CopyConfig(
        enabled=bool(section.get("enabled", True)),
        min_trader_sol=float(section.get("min_trader_sol", 0.02)),
        copy_ratio=float(section.get("copy_ratio", 0.25)),
        max_wallets=int(section.get("max_wallets", 20)),
        copy_boost=int(section.get("copy_boost", 25)),
        min_trader_win_rate=float(section.get("min_trader_win_rate", 0.55)),
        wallets=wallets,
    )
