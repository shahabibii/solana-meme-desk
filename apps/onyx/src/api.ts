import type { DeskMode } from "./store";

const BASE = "";

export async function fetchStatus(): Promise<Record<string, unknown>> {
  const r = await fetch(`${BASE}/api/status`);
  return r.json();
}

export async function fetchMode(): Promise<{ mode: DeskMode; live_ready: boolean }> {
  const r = await fetch(`${BASE}/api/mode`);
  return r.json();
}

export async function fetchEquityCurve(): Promise<{ points: { ts: string; equity_sol: number }[] }> {
  const r = await fetch(`${BASE}/api/equity-curve`);
  return r.json();
}

export async function fetchStats(): Promise<{
  total_trades: number;
  closed_trades: number;
  blocks: number;
  win_rate: number | null;
  avg_pnl_pct: number | null;
  total_pnl_pct: number;
}> {
  const r = await fetch(`${BASE}/api/stats`);
  return r.json();
}

export async function runLearner(): Promise<{ weights: Record<string, number> }> {
  const r = await fetch(`${BASE}/api/learner/run`, { method: "POST" });
  return r.json();
}

export async function runBacktest(): Promise<Record<string, unknown>> {
  const r = await fetch(`${BASE}/api/backtest/run`, { method: "POST" });
  return r.json();
}

export async function fetchIntegrations(): Promise<{
  integrations: Record<string, { active?: boolean; ready?: boolean }>;
}> {
  const r = await fetch(`${BASE}/api/integrations`);
  return r.json();
}

export async function chatOnyx(text: string): Promise<{ reply: string }> {
  const r = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  return r.json();
}

export async function setMode(mode: DeskMode, confirm = false): Promise<void> {
  const r = await fetch(`${BASE}/api/mode`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, confirm }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? r.statusText);
  }
}

export function connectOnyx(onMessage: (data: Record<string, unknown>) => void): WebSocket {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/onyx`);
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data as string));
    } catch {
      /* ignore */
    }
  };
  return ws;
}
