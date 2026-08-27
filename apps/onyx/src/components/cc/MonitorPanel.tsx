const CIRC = 163.4;

function Ring({
  pct,
  color,
  label,
}: {
  pct: number;
  color: string;
  label: string;
}) {
  const clamped = Math.max(0, Math.min(100, pct));
  const offset = CIRC - (CIRC * clamped) / 100;
  return (
    <div className="ring">
      <svg viewBox="0 0 62 62">
        <circle className="rbg" cx="31" cy="31" r="26" />
        <circle
          className="rfg"
          cx="31"
          cy="31"
          r="26"
          stroke={color}
          strokeDasharray={CIRC}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="rv">{Number.isFinite(pct) ? `${Math.round(clamped)}%` : "—"}</div>
      <div className="rk">{label}</div>
    </div>
  );
}

export default function MonitorPanel({
  winRate,
  exposure,
  safetyW,
  trades,
  blocks,
  avgPnl,
}: {
  winRate: number | null;
  exposure: number;
  safetyW: number;
  trades: number;
  blocks: number;
  avgPnl: number | null;
}) {
  const winPct = winRate != null ? winRate * 100 : 0;
  const avgStr =
    avgPnl == null || !Number.isFinite(avgPnl)
      ? "—"
      : `${avgPnl >= 0 ? "+" : ""}${avgPnl.toFixed(1)}%`;

  return (
    <div className="p monitor" style={{ ["--i" as string]: 7 }}>
      <div className="ph">
        <i />
        Desk Monitor
        <span className="tail" />
      </div>
      <div className="rings">
        <Ring pct={winPct} color="#7CF5B3" label="WIN RATE" />
        <Ring pct={exposure} color="#B09AD0" label="EXPOSURE" />
        <Ring pct={safetyW * 100} color="#7BE8FF" label="SAFETY W" />
      </div>
      <div className="mstats">
        <div>
          <div className="k">TRADES</div>
          <div className="v">{trades || "—"}</div>
        </div>
        <div>
          <div className="k">BLOCKS</div>
          <div className="v">{blocks || "—"}</div>
        </div>
        <div>
          <div className="k">AVG PNL</div>
          <div className={`v ${avgPnl != null && avgPnl >= 0 ? "up" : avgPnl != null ? "dn" : ""}`}>
            {avgStr}
          </div>
        </div>
      </div>
    </div>
  );
}
