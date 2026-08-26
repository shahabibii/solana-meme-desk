import { create } from "zustand";

export type DeskMode = "paper" | "live";

export type AgentState = {
  id: string;
  label: string;
  status: "idle" | "running" | "pass" | "block" | "trade";
  lastMs?: number;
  lastVerdict?: string;
};

export type FeedItem = {
  id: string;
  ts: string;
  kind: string;
  text: string;
  mint?: string;
};

export type Position = {
  mint: string;
  symbol: string;
  entry_sol: number;
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
  selectedMint: string | null;
  chartPoints: number[];
  busyAgent: string | null;
  setMode: (m: DeskMode) => void;
  setLiveReady: (v: boolean) => void;
  setConnected: (v: boolean) => void;
  applyStatus: (p: Record<string, unknown>) => void;
  pushFeed: (item: FeedItem) => void;
  setAgentRunning: (id: string) => void;
  setAgentDone: (id: string, verdict: string, ms: number) => void;
  selectMint: (mint: string | null) => void;
  pushChart: (v: number) => void;
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
  selectedMint: null,
  chartPoints: [50, 52, 48, 55, 58, 54, 62, 65, 61, 68],
  busyAgent: null,
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
      });
    }
    if (typeof p.mode === "string") set({ mode: p.mode as DeskMode });
  },
  pushFeed: (item) =>
    set((s) => ({ feed: [item, ...s.feed].slice(0, 80) })),
  setAgentRunning: (id) =>
    set((s) => ({
      busyAgent: id,
      agents: s.agents.map((a) =>
        a.id === id ? { ...a, status: "running" } : a
      ),
    })),
  setAgentDone: (id, verdict, ms) => {
    const status =
      verdict === "BLOCK"
        ? "block"
        : verdict === "FILLED" || verdict === "SUBMITTED"
          ? "trade"
          : verdict === "PASS" || verdict === "TRADE"
            ? "pass"
            : "idle";
    set((s) => ({
      busyAgent: s.busyAgent === id ? null : s.busyAgent,
      agents: s.agents.map((a) =>
        a.id === id ? { ...a, status, lastMs: ms, lastVerdict: verdict } : a
      ),
    }));
  },
  selectMint: (mint) => set({ selectedMint: mint }),
  pushChart: (v) =>
    set((s) => ({ chartPoints: [...s.chartPoints.slice(-39), v] })),
}));
