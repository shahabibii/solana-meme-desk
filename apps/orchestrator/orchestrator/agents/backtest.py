"""Backtest closed trades from journal — VectorBT when installed, else simple stats."""

from __future__ import annotations

from typing import Any

from orchestrator.journal.store import JournalStore


def _round_trips(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair sells with their preceding buy per mint (FIFO)."""
    open_buys: dict[str, list[dict[str, Any]]] = {}
    rounds: list[dict[str, Any]] = []
    for t in reversed(trades):
        mint = str(t.get("mint") or "")
        side = t.get("side")
        if side == "buy":
            open_buys.setdefault(mint, []).append(t)
        elif side == "sell" and t.get("pnl_pct") is not None:
            buys = open_buys.get(mint) or []
            buy = buys.pop() if buys else None
            rounds.append(
                {
                    "mint": mint,
                    "source": (buy or t).get("source") or "pump",
                    "pnl_pct": float(t["pnl_pct"]),
                    "sol": float(t.get("sol") or 0),
                    "mode": t.get("mode") or "paper",
                }
            )
    return list(reversed(rounds))


def run_backtest(journal: JournalStore) -> dict[str, Any]:
    trades = journal.recent_trades(500)
    rounds = _round_trips(trades)
    if not rounds:
        return {
            "engine": "none",
            "round_trips": 0,
            "message": "No closed round-trips in journal yet",
        }

    try:
        import numpy as np
        import pandas as pd

        returns = pd.Series([r["pnl_pct"] / 100.0 for r in rounds])
        cum = (1 + returns).cumprod()
        sharpe = float(returns.mean() / returns.std() * (252**0.5)) if returns.std() > 0 else 0.0

        result: dict[str, Any] = {
            "engine": "pandas",
            "round_trips": len(rounds),
            "total_return_pct": float((cum.iloc[-1] - 1) * 100) if len(cum) else 0.0,
            "win_rate": float((returns > 0).mean()),
            "avg_return_pct": float(returns.mean() * 100),
            "sharpe_approx": round(sharpe, 3),
            "max_drawdown_pct": float(((cum / cum.cummax()) - 1).min() * 100),
            "by_source": {},
        }

        try:
            import vectorbt as vbt

            pf = vbt.Portfolio.from_holding(
                close=pd.Series(cum.values, index=pd.RangeIndex(len(cum))),
                init_cash=1.0,
            )
            result["engine"] = "vectorbt"
            result["vectorbt"] = {
                "total_return_pct": float(pf.total_return() * 100),
                "max_drawdown_pct": float(pf.max_drawdown() * 100),
            }
        except Exception:
            pass

        by_src: dict[str, list[float]] = {}
        for r in rounds:
            by_src.setdefault(str(r["source"]), []).append(float(r["pnl_pct"]))
        result["by_source"] = {
            k: {"n": len(v), "avg_pnl_pct": sum(v) / len(v)} for k, v in by_src.items()
        }
        return result
    except ImportError:
        pnls = [r["pnl_pct"] for r in rounds]
        wins = [p for p in pnls if p > 0]
        return {
            "engine": "simple",
            "round_trips": len(rounds),
            "win_rate": len(wins) / len(pnls),
            "avg_pnl_pct": sum(pnls) / len(pnls),
            "total_pnl_pct": sum(pnls),
        }
