import { create } from "zustand";
import { FEED_CAP, FILLS_CAP } from "./config";

export type DeskMode = "paper" | "live";

export type AgentState = {
  id: string;
  label: string;
  status: "idle" | "running" | "pass" | "block" | "trade";
  lastMs?: number;
  lastVerdict?: string;
  blockReasons?: string[];
};

export type FeedKind = "cand" | "blk" | "fill" | "mode" | "ag";

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

export const useDesk = create<DeskState>((set, get) => ({
  mode: "paper",
  liveReady: false,
  connected: false,
  equitySol: 1,
  cashSol: 1,
  positions: [],
  agents: AGENT_IDS.map((a) => ({ ...a, status: "idle" as const })),
  feed: [],
  recentFills: [],
  selectedMint: null,
  chartPoints: [0, 2, -1, 4, 6, 3, 8, 5, 7, 4],
  busyAgent: null,
  lastScore: null,
  stats: null,
  equityPoints: [],
  learnerWeights: { pump: 1, fomo: 1, convergence: 1.2, copy: 1.15, safety: 1 },
  fomoEnabled: false,
  fomoCopyMode: false,
  copyWalletCount: 0,
  fomoFollowCount: 0,
  copyWatchlist: [],
  copeReachable: null,
  copeError: null,
  onChainSol: null,
  sniperHealth: null,
  paused: false,
  integrations: null,
  walletPubkey: null,
  setMode: (m) => set({ mode: m }),
  setLiveReady: (v) => set({ liveReady: v }),
  setConnected: (v) => set({ connected: v }),
  applyStatus: (p) => {
    const wallet = p.wallet as Record<string, unknown> | undefined;
    if (wallet) {
      set({
        equitySol: Number(wallet.equity_sol ?? get().equitySol),
        cashSol: Number(wallet.cash_sol ?? get().cashSol),
        positions: (wallet.positions as Position[]) ?? [],
        onChainSol:
          wallet.on_chain_sol != null ? Number(wallet.on_chain_sol) : get().onChainSol,
      });
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
  setEquityPoints: (points) => set({ equityPoints: points }),
  setLastScore: (n) => set({ lastScore: n }),
}));
