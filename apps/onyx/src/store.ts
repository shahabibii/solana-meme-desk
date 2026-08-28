import { create } from "zustand";
import { FEED_CAP, FILLS_CAP } from "./config";
import {
  loadSession,
  type ApiTrade,
  tradesToFeed,
  tradesToFills,
} from "./persist";

export type DeskMode = "paper" | "live";

export type AgentState = {
  id: string;
  label: string;
  status: "idle" | "running" | "pass" | "block" | "trade";
  lastMs?: number;
  lastVerdict?: string;
  blockReasons?: string[];
};

export type FeedKind = "cand" | "blk" | "fill" | "mode" | "ag" | "watch" | "skip";

export type FeedItem = {
  id: string;
  ts: string;
  kind: FeedKind;
  text: string;
  sub?: string;
  mint?: string;
  sev: "info" | "warn" | "live" | "mode";
};

export type RecentFill = {
  id: string;
  symbol: string;
  sol: number;
  side: string;
  ts: string;
};

export type TradeRow = {
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

export type CopyWatchEntry = {
  handle: string;
  wallet: string;
  wallet_short: string;
};

export type Position = {
  mint: string;
  symbol: string;
  entry_sol: number;
  upnl_pct?: number | null;
  source?: string;
  safety_score?: number;
};

type DeskState = {
  mode: DeskMode;
  liveReady: boolean;
  connected: boolean;
  equitySol: number;
  cashSol: number;
  positions: Position[];
  agents: AgentState[];
  feed: FeedItem[];
  recentFills: RecentFill[];
  recentTrades: TradeRow[];
  selectedMint: string | null;
  chartPoints: number[];
  busyAgent: string | null;
  lastScore: number | null;
  stats: Record<string, unknown> | null;
  equityPoints: { ts: string; equity_sol: number }[];
  learnerWeights: Record<string, number>;
  fomoEnabled: boolean;
  fomoCopyMode: boolean;
  copyWalletCount: number;
  fomoFollowCount: number;
  copyWatchlist: CopyWatchEntry[];
  copeReachable: boolean | null;
  copeError: string | null;
  onChainSol: number | null;
  sniperHealth: Record<string, unknown> | null;
  paused: boolean;
  integrations: Record<string, { active?: boolean; ready?: boolean }> | null;
  walletPubkey: string | null;
  setMode: (m: DeskMode) => void;
  setLiveReady: (v: boolean) => void;
  setConnected: (v: boolean) => void;
  applyStatus: (p: Record<string, unknown>) => void;
  hydrateFromBoot: (
    trades: Record<string, unknown>[],
    equityPoints: { ts: string; equity_sol: number }[]
  ) => void;
  pushFeed: (item: FeedItem) => void;
  pushFill: (fill: RecentFill) => void;
  setAgentRunning: (id: string) => void;
  setAgentDone: (id: string, verdict: string, ms: number, reasons?: string[]) => void;
  decayAgent: (id: string) => void;
  selectMint: (mint: string | null) => void;
  pushChart: (v: number) => void;
  setEquityPoints: (points: { ts: string; equity_sol: number }[]) => void;
  setLastScore: (n: number | null) => void;
};

const AGENT_IDS = [
  { id: "scout", label: "Scout" },
  { id: "safety", label: "Safety" },
  { id: "copy", label: "Copy" },
  { id: "research", label: "Research" },
  { id: "scorer", label: "Scorer" },
  { id: "executor", label: "Executor" },
  { id: "learner", label: "Learner" },
];

const cached = loadSession();

function mergeFeed(existing: FeedItem[], incoming: FeedItem[]): FeedItem[] {
  const seen = new Set(existing.map((f) => f.id));
  const merged = [...existing];
  for (const item of incoming) {
    if (!seen.has(item.id)) {
      seen.add(item.id);
      merged.push(item);
    }
  }
  return merged.sort((a, b) => b.ts.localeCompare(a.ts)).slice(0, FEED_CAP);
}

function mergeFills(existing: RecentFill[], incoming: RecentFill[]): RecentFill[] {
  const seen = new Set(existing.map((f) => f.id));
  const merged = [...existing];
  for (const fill of incoming) {
    if (!seen.has(fill.id)) {
      seen.add(fill.id);
      merged.push(fill);
    }
  }
  return merged.sort((a, b) => b.ts.localeCompare(a.ts)).slice(0, FILLS_CAP);
}

export const useDesk = create<DeskState>((set, get) => ({
  mode: (cached?.mode as DeskMode) ?? "paper",
  liveReady: false,
  connected: false,
  equitySol: cached?.equitySol ?? 1,
  cashSol: cached?.cashSol ?? 1,
  positions: cached?.positions ?? [],
  agents: AGENT_IDS.map((a) => ({ ...a, status: "idle" as const })),
  feed: cached?.feed ?? [],
  recentFills: cached?.recentFills ?? [],
  recentTrades: [],
  selectedMint: cached?.selectedMint ?? null,
  chartPoints: cached?.chartPoints?.length ? cached.chartPoints : [0, 2, -1, 4, 6, 3, 8, 5, 7, 4],
  busyAgent: null,
  lastScore: null,
  stats: cached?.stats ?? null,
  equityPoints: cached?.equityPoints ?? [],
  learnerWeights: cached?.learnerWeights ?? {
    pump: 1,
    fomo: 1,
    convergence: 1.2,
    copy: 1.15,
    safety: 1,
  },
  fomoEnabled: false,
  fomoCopyMode: false,
  copyWalletCount: 0,
  fomoFollowCount: 0,
  copyWatchlist: [],
  copeReachable: null,
  copeError: null,
  onChainSol: cached?.onChainSol ?? null,
  sniperHealth: null,
  paused: false,
  integrations: null,
  walletPubkey: null,
  setMode: (m) => set({ mode: m }),
  setLiveReady: (v) => set({ liveReady: v }),
  setConnected: (v) => set({ connected: v }),
  hydrateFromBoot: (trades, equityPoints) => {
    const rows = trades as TradeRow[];
    const apiTrades = rows as unknown as ApiTrade[];
    const fromFeed = tradesToFeed(apiTrades);
    const fromFills = tradesToFills(apiTrades);
    set((s) => {
      const upnlChart = s.positions
        .map((p) => p.upnl_pct)
        .filter((v): v is number => v != null);
      const tradeIds = new Set(fromFeed.map((f) => f.id));
      const liveOnly = s.feed.filter((f) => !f.id.startsWith("trade-"));
      const feed =
        fromFeed.length > 0
          ? mergeFeed(mergeFeed(fromFeed, liveOnly), s.feed.filter((f) => tradeIds.has(f.id)))
          : mergeFeed(s.feed, fromFeed);
      return {
        recentTrades: rows,
        feed,
        recentFills:
          fromFills.length > 0 ? mergeFills([], fromFills) : mergeFills(s.recentFills, fromFills),
        equityPoints: equityPoints.length > 0 ? equityPoints : s.equityPoints,
        chartPoints:
          upnlChart.length >= 2
            ? upnlChart
            : s.chartPoints.length >= 2
              ? s.chartPoints
              : [s.equitySol * 0.98, s.equitySol],
      };
    });
  },
  applyStatus: (p) => {
    const wallet = p.wallet as Record<string, unknown> | undefined;
    if (wallet) {
      const positions = Array.isArray(wallet.positions)
        ? (wallet.positions as Position[])
        : get().positions;
      set({
        equitySol:
          wallet.equity_sol != null ? Number(wallet.equity_sol) : get().equitySol,
        cashSol: wallet.cash_sol != null ? Number(wallet.cash_sol) : get().cashSol,
        positions,
        onChainSol:
          wallet.on_chain_sol != null ? Number(wallet.on_chain_sol) : get().onChainSol,
      });
      const upnl = positions
        .map((pos) => pos.upnl_pct)
        .filter((v): v is number => v != null);
      if (upnl.length >= 2) {
        set({ chartPoints: upnl });
      }
    }
    const integ = p.integrations as
      | Record<string, { active?: boolean; ready?: boolean; pubkey?: string }>
      | undefined;
    if (integ?.live_wallet?.pubkey) {
      set({ walletPubkey: String(integ.live_wallet.pubkey) });
    }
    if (typeof p.mode === "string") set({ mode: p.mode as DeskMode });
    if (p.stats) set({ stats: p.stats as Record<string, unknown> });
    if (p.learner_weights)
      set({ learnerWeights: p.learner_weights as Record<string, number> });
    if (typeof p.fomo_enabled === "boolean") set({ fomoEnabled: p.fomo_enabled });
    if (typeof p.fomo_copy_mode === "boolean") set({ fomoCopyMode: p.fomo_copy_mode });
    const ct = p.copy_trading as {
      wallets?: number;
      cope_error?: string | null;
      copy_watchlist?: CopyWatchEntry[];
    } | undefined;
    if (ct && typeof ct.wallets === "number") set({ copyWalletCount: ct.wallets });
    if (ct?.copy_watchlist) set({ copyWatchlist: ct.copy_watchlist });
    if (Array.isArray(p.fomo_follow_handles))
      set({ fomoFollowCount: p.fomo_follow_handles.length });
    else if (ct && typeof ct.manual_follows === "number")
      set({ fomoFollowCount: ct.manual_follows });
    const ch = p.cope_health as { reachable?: boolean; error?: string } | undefined;
    if (ch) {
      set({
        copeReachable: Boolean(ch.reachable),
        copeError: ch.error ?? ct?.cope_error ?? null,
      });
    } else if (ct?.cope_error) {
      set({ copeError: ct.cope_error });
    }
    if (p.sniper_health) set({ sniperHealth: p.sniper_health as Record<string, unknown> });
    if (typeof p.paused === "boolean") set({ paused: p.paused });
    if (p.integrations)
      set({ integrations: p.integrations as Record<string, { active?: boolean }> });
    if (typeof p.live_ready === "boolean") set({ liveReady: p.live_ready });
  },
  pushFeed: (item) => set((s) => ({ feed: [item, ...s.feed].slice(0, FEED_CAP) })),
  pushFill: (fill) =>
    set((s) => ({ recentFills: [fill, ...s.recentFills].slice(0, FILLS_CAP) })),
  setAgentRunning: (id) =>
    set((s) => ({
      busyAgent: id,
      agents: s.agents.map((a) => (a.id === id ? { ...a, status: "running" } : a)),
    })),
  setAgentDone: (id, verdict, ms, reasons) => {
    const status =
      verdict === "BLOCK"
        ? "block"
        : verdict === "FILLED" || verdict === "SUBMITTED"
          ? "trade"
          : verdict === "PASS" ||
              verdict === "TRADE" ||
              verdict === "BOOST" ||
              verdict === "NEUTRAL" ||
              verdict === "SKIP"
            ? "pass"
            : "idle";
    set((s) => ({
      busyAgent: s.busyAgent === id ? null : s.busyAgent,
      agents: s.agents.map((a) =>
        a.id === id
          ? {
              ...a,
              status,
              lastMs: ms,
              lastVerdict: verdict,
              blockReasons: reasons,
            }
          : a
      ),
    }));
  },
  decayAgent: (id) =>
    set((s) => ({
      agents: s.agents.map((a) =>
        a.id === id && a.status !== "running" ? { ...a, status: "idle" } : a
      ),
    })),
  selectMint: (mint) => set({ selectedMint: mint }),
  pushChart: (v) => set((s) => ({ chartPoints: [...s.chartPoints.slice(-39), v] })),
  setEquityPoints: (points) => set({ equityPoints: points.length ? points : get().equityPoints }),
  setLastScore: (n) => set({ lastScore: n }),
}));
