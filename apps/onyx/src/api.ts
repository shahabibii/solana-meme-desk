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
