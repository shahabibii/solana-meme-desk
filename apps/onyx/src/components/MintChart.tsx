import type { Position } from "../store";

export default function MintChart({
  points,
  mint,
  positions,
}: {
  points: number[];
  mint: string | null;
  positions: Position[];
}) {
  const pos = positions.find((p) => p.mint === mint);
  const w = 320;
  const h = 120;
  const series = points.length ? points : [0, 0];
  const min = Math.min(...series, -5);
  const max = Math.max(...series, 5);
  const range = max - min || 1;
  const coords = series
    .map((v, i) => {
      const x = (i / Math.max(series.length - 1, 1)) * w;
      const y = h - ((v - min) / range) * (h - 10) - 5;
      return `${x},${y}`;
    })
    .join(" ");
  const upnl = pos?.upnl_pct ?? series[series.length - 1] ?? null;

  return (
    <div className="mint-panel glass">
      <header>
        <h2>{pos?.symbol ?? "Mint chart"}</h2>
        {upnl != null && (
          <span className={`mint-upnl ${upnl >= 0 ? "up" : "down"}`}>
            {upnl >= 0 ? "+" : ""}
            {Number(upnl).toFixed(1)}%
          </span>
        )}
      </header>
      {!mint ? (
        <p className="muted tiny">Select a position or feed mint</p>
      ) : (
        <svg viewBox={`0 0 ${w} ${h}`} className="chart-svg" preserveAspectRatio="none">
          <defs>
            <linearGradient id="mintGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(123,232,255,0.3)" />
              <stop offset="100%" stopColor="rgba(123,232,255,0)" />
            </linearGradient>
          </defs>
          <polygon points={`0,${h} ${coords} ${w},${h}`} fill="url(#mintGrad)" />
          <polyline points={coords} fill="none" stroke="var(--cyan)" strokeWidth="2" />
        </svg>
      )}
      {mint && (
        <code className="tiny muted">{mint.slice(0, 12)}…</code>
      )}
    </div>
  );
}
