/** Browser session persistence — survives page refresh (same tab/origin). */

import type { DeskMode, FeedItem, Position, RecentFill } from "./store";
import { FEED_CAP, FILLS_CAP } from "./config";

const KEY = "onyx_desk_session_v1";

export type PersistedSession = {
  savedAt: string;
  mode: DeskMode;
  equitySol: number;
  cashSol: number;
  onChainSol: number | null;
  positions: Position[];
  feed: FeedItem[];
  recentFills: RecentFill[];
  equityPoints: { ts: string; equity_sol: number }[];
  stats: Record<string, unknown> | null;
  learnerWeights: Record<string, number>;
  selectedMint: string | null;
  chartPoints: number[];
};

export function loadSession(): Partial<PersistedSession> | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PersistedSession;
  } catch {
    return null;
  }
}

export function saveSession(data: PersistedSession): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(data));
  } catch {
    /* quota / private mode */
  }
}

export function buildSessionSnapshot(state: {
  mode: DeskMode;
  equitySol: number;
  cashSol: number;
  onChainSol: number | null;
  positions: Position[];
  feed: FeedItem[];
  recentFills: RecentFill[];
  equityPoints: { ts: string; equity_sol: number }[];
  stats: Record<string, unknown> | null;
  learnerWeights: Record<string, number>;
  selectedMint: string | null;
  chartPoints: number[];
}): PersistedSession {
  return {
    savedAt: new Date().toISOString(),
    mode: state.mode,
    equitySol: state.equitySol,
    cashSol: state.cashSol,
    onChainSol: state.onChainSol,
    positions: state.positions,
    feed: state.feed.slice(0, FEED_CAP),
    recentFills: state.recentFills.slice(0, FILLS_CAP),
    equityPoints: state.equityPoints.slice(-120),
    stats: state.stats,
    learnerWeights: state.learnerWeights,
    selectedMint: state.selectedMint,
    chartPoints: state.chartPoints.slice(-40),
  };
}

export type ApiTrade = {
  id: number;
  ts: string;
  mint: string;
  symbol: string;
  side: string;
  sol: number;
  pnl_pct: number | null;
  mode: string;
  source: string;
};

export function tradesToFills(trades: ApiTrade[]): RecentFill[] {
  return trades.slice(0, FILLS_CAP).map((t) => ({
    id: `trade-${t.id}`,
    symbol: t.symbol || t.mint.slice(0, 6),
    sol: Number(t.sol),
    side: t.side,
    ts: t.ts,
  }));
}

export function tradesToFeed(trades: ApiTrade[]): FeedItem[] {
  return trades.slice(0, FEED_CAP).map((t) => {
    const pnl =
      t.pnl_pct != null
        ? ` · ${t.pnl_pct >= 0 ? "+" : ""}${t.pnl_pct.toFixed(1)}%`
        : "";
    return {
      id: `trade-${t.id}`,
      ts: t.ts,
      kind: "fill" as const,
      sev: "live" as const,
      mint: t.mint,
      text: `${t.side.toUpperCase()} $${t.symbol} · ${Number(t.sol).toFixed(3)} ◎${pnl}`,
      sub: `${t.source} · ${t.mode}`,
    };
  });
}
