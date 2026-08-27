/** Central endpoint config — adjust paths here without touching components. */

export const API = {
  status: "/api/status",
  mode: "/api/mode",
  equityCurve: "/api/equity-curve",
  stats: "/api/stats",
  integrations: "/api/integrations",
  chat: "/api/chat",
  trades: "/api/trades",
  learnerRun: "/api/learner/run",
  backtestRun: "/api/backtest/run",
  deskPause: "/api/desk/pause",
  copyRefresh: "/api/copy/refresh",
  voice: "/api/voice",
  tts: "/api/tts",
} as const;

export function wsOnyxUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws/onyx`;
}

export const POLL_MS = 15_000;
export const AGENT_DECAY_MS = 2_500;
export const FEED_CAP = 40;
export const FILLS_CAP = 6;
export const BLOCK_SPEAK_THROTTLE_MS = 120_000;
