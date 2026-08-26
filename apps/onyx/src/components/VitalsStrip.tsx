export default function VitalsStrip({
  mode,
  connected,
  liveReady,
  busyAgent,
  blocks,
  trades,
  openPositions,
}: {
  mode: string;
  connected: boolean;
  liveReady: boolean;
  busyAgent: string | null;
  blocks: number;
  trades: number;
  openPositions: number;
}) {
  return (
    <div className="vitals-strip" aria-label="Desk vitals">
      <span className={`vital ${mode === "live" ? "live" : "paper"}`}>
        {mode.toUpperCase()}
        {mode === "live" && !liveReady ? " · wallet?" : ""}
      </span>
      <span className={`vital ${connected ? "ok" : "bad"}`}>
        {connected ? "STREAM OK" : "RECONNECTING"}
      </span>
      <span className="vital">{busyAgent ? `${busyAgent.toUpperCase()}…` : "IDLE"}</span>
      <span className="vital">{blocks} blocks</span>
      <span className="vital">{trades} trades</span>
      <span className="vital">{openPositions} open</span>
    </div>
  );
}
