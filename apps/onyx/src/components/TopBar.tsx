import { OnyxLogoMark } from "./OnyxOrb";

export default function TopBar({
  mode,
  modeBusy,
  liveReady,
  connected,
  equitySol,
  cashSol,
  onChainSol,
  pubkey,
  busyAgent,
  blocks,
  trades,
  openPositions,
  onModePaper,
  onModeLive,
  onCopyPubkey,
}: {
  mode: "paper" | "live";
  modeBusy: boolean;
  liveReady: boolean;
  connected: boolean;
  equitySol: number;
  cashSol: number;
  onChainSol: number | null;
  pubkey: string | null;
  busyAgent: string | null;
  blocks: number;
  trades: number;
  openPositions: number;
  onModePaper: () => void;
  onModeLive: () => void;
  onCopyPubkey: () => void;
}) {
  const displayEquity =
    mode === "live" && onChainSol != null ? onChainSol : equitySol;

  return (
    <header className="top-bar">
      <div className="brand">
        <OnyxLogoMark />
        <h1>ONYX</h1>
      </div>

      <div className="mode-seg" role="group" aria-label="Desk mode">
        <button
          type="button"
          className={mode === "paper" ? "active paper" : ""}
          onClick={onModePaper}
          disabled={modeBusy || mode === "paper"}
        >
          Paper
        </button>
        <button
          type="button"
          className={mode === "live" ? "active live" : ""}
          onClick={onModeLive}
          disabled={modeBusy || mode === "live"}
        >
          Live
        </button>
      </div>

      <div className="vital-chip">
        <span className={`dot ${liveReady ? "ok" : "warn"}`} />
        <span>{liveReady ? "LIVE ARMED" : "WALLET NOT READY"}</span>
      </div>

      <div className="vital-chip">
        <span className={`dot ${connected ? "ok" : "warn"}`} />
        <span>{connected ? "stream" : "reconnecting"}</span>
      </div>

      <div className="vital-chip">
        <strong>{displayEquity.toFixed(3)}</strong> SOL
      </div>

      <div className="vital-chip">
        cash <strong>{cashSol.toFixed(3)}</strong>
      </div>

      {pubkey && (
        <button type="button" className="pubkey-btn" onClick={onCopyPubkey} title="Copy pubkey">
          {pubkey.slice(0, 8)}…
        </button>
      )}

      <div className="top-spacer" />

      <div className={`busy-agent orbitron ${busyAgent ? "" : "idle"}`}>
        {busyAgent ? busyAgent.toUpperCase() : "IDLE"}
      </div>

      <div className="vital-chip">
        {blocks} blocks · {trades} trades · {openPositions} open
      </div>
    </header>
  );
}
