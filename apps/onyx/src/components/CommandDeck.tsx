import { useState } from "react";
import {
  chatOnyx,
  fetchIntegrations,
  fetchStatus,
  runBacktest,
  runLearner,
} from "../api";

export default function CommandDeck({
  onNotify,
  onRefresh,
}: {
  onNotify: (text: string) => void;
  onRefresh: (status: Record<string, unknown>) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);

  async function run(label: string, fn: () => Promise<void>) {
    if (busy) return;
    setBusy(label);
    try {
      await fn();
    } catch (e) {
      onNotify(e instanceof Error ? e.message : `${label} failed`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="command-deck">
      <h2>Command deck</h2>
      <div className="deck-grid">
        <button
          type="button"
          disabled={!!busy}
          onClick={() =>
            void run("status", async () => {
              const s = await fetchStatus();
              onRefresh(s);
              const st = s.stats as { blocks?: number; total_trades?: number } | undefined;
              const w = s.wallet as { open_positions?: number; equity_sol?: number } | undefined;
              onNotify(
                `${String(s.mode).toUpperCase()} · ${Number(w?.equity_sol ?? 0).toFixed(3)} SOL · ${w?.open_positions ?? 0} open · ${st?.blocks ?? 0} blocks · ${st?.total_trades ?? 0} trades`
              );
            })
          }
        >
          {busy === "status" ? "…" : "Status"}
        </button>
        <button
          type="button"
          disabled={!!busy}
          onClick={() =>
            void run("learner", async () => {
              const r = await runLearner();
              onRefresh(await fetchStatus());
              onNotify(`Learner updated: ${Object.entries(r.weights).map(([k, v]) => `${k}=${v.toFixed(2)}`).join(", ")}`);
            })
          }
        >
          {busy === "learner" ? "…" : "Run learner"}
        </button>
        <button
          type="button"
          disabled={!!busy}
          onClick={() =>
            void run("backtest", async () => {
              const r = await runBacktest();
              const n = Number(r.round_trips ?? 0);
              onNotify(
                n
                  ? `Backtest: ${n} round-trips, win ${((Number(r.win_rate ?? 0)) * 100).toFixed(0)}%`
                  : String(r.message ?? "No closed trades yet")
              );
            })
          }
        >
          {busy === "backtest" ? "…" : "Backtest"}
        </button>
        <button
          type="button"
          disabled={!!busy}
          onClick={() =>
            void run("keys", async () => {
              const i = await fetchIntegrations();
              const active = Object.entries(i.integrations)
                .filter(([, v]) => v.active)
                .map(([k]) => k.replace(/_/g, " "));
              onNotify(`Active: ${active.join(", ") || "RPC only"}`);
            })
          }
        >
          {busy === "keys" ? "…" : "Keys"}
        </button>
        <button
          type="button"
          disabled={!!busy}
          onClick={() =>
            void run("blocks", async () => {
              const { reply } = await chatOnyx("blocks");
              onNotify(reply);
            })
          }
        >
          {busy === "blocks" ? "…" : "Why blocks?"}
        </button>
      </div>
    </div>
  );
}
