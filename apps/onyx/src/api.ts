import type { DeskMode } from "./store";
import { API, wsOnyxUrl } from "./config";

export type VoiceConfig = {
  name: string;
  label: string;
  voice_id?: string;
  provider: "elevenlabs" | "browser";
  active: boolean;
  preview_url: string;
};

export async function fetchVoiceConfig(): Promise<VoiceConfig> {
  const r = await fetch(API.voice);
  if (!r.ok) {
    return {
      name: "Maisie",
      label: "Maisie — friendly casual neighbor",
      provider: "browser",
      active: false,
      preview_url: "/voices/maisie-preview.mp3",
    };
  }
  return r.json();
}

export async function synthesizeSpeech(text: string): Promise<Blob> {
  const r = await fetch(API.tts, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? r.statusText);
  }
  return r.blob();
}

export async function setDeskPaused(paused: boolean): Promise<{ paused: boolean; message: string }> {
  const r = await fetch(API.deskPause, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paused }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function stopDesk(): Promise<{ paused: boolean; message: string }> {
  const r = await fetch(API.deskStop, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function resumeDesk(): Promise<{ paused: boolean; message: string }> {
  const r = await fetch(API.deskResume, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function armLiveDesk(): Promise<{
  mode: DeskMode;
  paused: boolean;
  message: string;
  live_ready: boolean;
}> {
  const r = await fetch(API.deskArmLive, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm: true }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? r.statusText);
  }
  return r.json();
}

export async function refreshCopyWallets(): Promise<{ count: number; wallets: string[] }> {
  const r = await fetch(API.copyRefresh, { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function bootstrapFomoCopy(): Promise<Record<string, unknown>> {
  const r = await fetch(API.fomoBootstrap, { method: "POST" });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? r.statusText);
  }
  return r.json();
}

export async function syncFomoProfile(
  fomoHandle: string
): Promise<Record<string, unknown>> {
  const r = await fetch(API.fomoSync, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fomo_handle: fomoHandle }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? r.statusText);
  }
  return r.json();
}

export async function fetchTrades(limit = 20): Promise<{ trades: Record<string, unknown>[] }> {
  const r = await fetch(`${API.trades}?limit=${limit}`);
  return r.json();
}

export async function fetchSession(): Promise<Record<string, unknown>> {
  const r = await fetch(API.session);
  return r.json();
}

export async function fetchStatus(): Promise<Record<string, unknown>> {
  const r = await fetch(API.status);
  return r.json();
}

export async function fetchMode(): Promise<{ mode: DeskMode; live_ready: boolean }> {
  const r = await fetch(API.mode);
  return r.json();
}

export async function fetchEquityCurve(): Promise<{ points: { ts: string; equity_sol: number }[] }> {
  const r = await fetch(API.equityCurve);
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
  const r = await fetch(API.stats);
  return r.json();
}

export async function runLearner(): Promise<{ weights: Record<string, number> }> {
  const r = await fetch(API.learnerRun, { method: "POST" });
  return r.json();
}

export async function runBacktest(): Promise<Record<string, unknown>> {
  const r = await fetch(API.backtestRun, { method: "POST" });
  return r.json();
}

export async function fetchIntegrations(): Promise<{
  integrations: Record<string, { active?: boolean; ready?: boolean }>;
}> {
  const r = await fetch(API.integrations);
  return r.json();
}

export async function chatOnyx(text: string): Promise<{ reply: string }> {
  const r = await fetch(API.chat, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  return r.json();
}

export async function setMode(mode: DeskMode, confirm = false): Promise<void> {
  const r = await fetch(API.mode, {
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
  const ws = new WebSocket(wsOnyxUrl());
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data as string));
    } catch {
      /* ignore */
    }
  };
  return ws;
}
