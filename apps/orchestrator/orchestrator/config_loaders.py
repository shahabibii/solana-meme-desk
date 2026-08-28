"""Load copy-trading and desk feed configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from orchestrator.copy_signals import CopyImprovementsConfig


@dataclass
class DeskFeedConfig:
    fomo_copy_mode: bool = False
    pump_launch_feed: bool = True
    helius_wallet_watch: bool = True
    cope_poll_sec: int = 60
    helius_poll_sec: float = 6.0
    allowed_sources: frozenset[str] = frozenset({"copy", "convergence", "fomo"})
    entry_min_score_default: int = 72
    entry_min_score_by_source: dict[str, int] = field(default_factory=dict)
    fomo_relay_backfill_minutes: int = 0
    copy_improvements: "CopyImprovementsConfig | None" = None


@dataclass
class CopyConfig:
    enabled: bool = True
    min_trader_sol: float = 0.02
    copy_ratio: float = 0.25
    max_wallets: int = 20
    copy_boost: int = 25
    min_trader_win_rate: float = 0.55
    wallets: list[str] = field(default_factory=list)


def load_copy_config(config_dir: Path, data_dir: Path | None = None) -> CopyConfig:
    path = config_dir / "copy_wallets.yaml"
    if not path.exists():
        cfg = CopyConfig()
    else:
        raw = yaml.safe_load(path.read_text()) or {}
        section = raw.get("copy") or {}
        wallets = [str(w) for w in (raw.get("wallets") or []) if w and len(str(w)) >= 32]
        cfg = CopyConfig(
            enabled=bool(section.get("enabled", True)),
            min_trader_sol=float(section.get("min_trader_sol", 0.02)),
            copy_ratio=float(section.get("copy_ratio", 0.25)),
            max_wallets=int(section.get("max_wallets", 20)),
            copy_boost=int(section.get("copy_boost", 25)),
            min_trader_win_rate=float(section.get("min_trader_win_rate", 0.55)),
            wallets=wallets,
        )
    if data_dir:
        runtime = data_dir / "copy_wallets.json"
        if runtime.exists():
            try:
                import json

                extra = json.loads(runtime.read_text())
                for w in extra.get("wallets") or []:
                    if w and len(str(w)) >= 32 and str(w) not in cfg.wallets:
                        cfg.wallets.append(str(w))
            except Exception:
                pass
    return cfg


@dataclass
class FomoFollowsConfig:
    owner: str | None = None
    handles: list[str] = field(default_factory=list)


def load_fomo_follows_config(config_dir: Path) -> FomoFollowsConfig:
    path = config_dir / "fomo_follows.yaml"
    if not path.exists():
        return FomoFollowsConfig()
    raw = yaml.safe_load(path.read_text()) or {}
    handles: list[str] = []
    seen: set[str] = set()
    for item in raw.get("follows") or []:
        h = str(item).strip().lstrip("@")
        if h and h not in seen:
            seen.add(h)
            handles.append(h)
    owner = raw.get("owner")
    return FomoFollowsConfig(
        owner=str(owner).strip().lstrip("@") if owner else None,
        handles=handles,
    )


def load_fomo_wallets_by_handle(config_dir: Path) -> dict[str, str]:
    """Handle → full SOL address from fomo_wallets.yaml and copy_wallets.yaml."""
    merged: dict[str, str] = {}
    for name in ("fomo_wallets.yaml", "copy_wallets.yaml"):
        path = config_dir / name
        if not path.exists():
            continue
        raw = yaml.safe_load(path.read_text()) or {}
        section = raw.get("wallets_by_handle") or raw.get("wallets_with_handles") or {}
        for handle, val in section.items():
            h = str(handle).strip().lstrip("@")
            w = str(val).strip()
            if h and len(w) >= 32:
                merged[h] = w
    return merged


def load_fomo_wallets(config_dir: Path) -> list[str]:
    """SOL wallets keyed by fomo handle — paste full addresses in fomo_wallets.yaml."""
    wallets: list[str] = []
    seen: set[str] = set()
    for w in load_fomo_wallets_by_handle(config_dir).values():
        if w not in seen:
            seen.add(w)
            wallets.append(w)
    return wallets


def load_desk_feed_config(config_dir: Path) -> DeskFeedConfig:
    path = config_dir / "desk.yaml"
    if not path.exists():
        return DeskFeedConfig()
    raw = yaml.safe_load(path.read_text()) or {}
    allowed = raw.get("allowed_sources") or ["copy", "convergence", "fomo"]
    scores = raw.get("entry_min_score") or {}
    default_score = int(scores.get("default", raw.get("entry_min_score_default", 72)))
    by_source = {
        k: int(v)
        for k, v in scores.items()
        if k != "default" and isinstance(v, (int, float))
    }
    fomo_mode = bool(raw.get("fomo_copy_mode", False))
    pump_feed = bool(raw.get("pump_launch_feed", not fomo_mode))
    if fomo_mode and "pump_launch_feed" not in raw:
        pump_feed = False
    imp_raw = raw.get("copy_improvements") or {}
    copy_improvements = CopyImprovementsConfig(
        convergence_window_sec=int(imp_raw.get("convergence_window_sec", 600)),
        convergence_min_wallets=int(imp_raw.get("convergence_min_wallets", 2)),
        require_convergence_for_copy=bool(imp_raw.get("require_convergence_for_copy", False)),
        convergence_boost_per_wallet=int(imp_raw.get("convergence_boost_per_wallet", 12)),
        convergence_size_step=float(imp_raw.get("convergence_size_step", 0.15)),
        convergence_size_cap=float(imp_raw.get("convergence_size_cap", 2.0)),
        mirror_sell_enabled=bool(imp_raw.get("mirror_sell_enabled", True)),
        mirror_sell_fraction=float(imp_raw.get("mirror_sell_fraction", 0.5)),
        mirror_sell_full_wallets=int(imp_raw.get("mirror_sell_full_wallets", 2)),
        retry_after_block=bool(imp_raw.get("retry_after_block", True)),
    )
    return DeskFeedConfig(
        fomo_copy_mode=fomo_mode,
        pump_launch_feed=pump_feed,
        helius_wallet_watch=bool(raw.get("helius_wallet_watch", True)),
        cope_poll_sec=int(raw.get("cope_poll_sec", 60)),
        helius_poll_sec=float(raw.get("helius_poll_sec", 6)),
        allowed_sources=frozenset(str(s) for s in allowed),
        entry_min_score_default=default_score,
        entry_min_score_by_source=by_source,
        copy_improvements=copy_improvements,
        fomo_relay_backfill_minutes=int(raw.get("fomo_relay_backfill_minutes", 0)),
    )


def save_runtime_wallets(data_dir: Path, wallets: list[str]) -> None:
    import json

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "copy_wallets.json").write_text(
        json.dumps({"wallets": wallets}, indent=2)
    )
