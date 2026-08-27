export default function EquityCurve({
  points,
}: {
  points: { ts: string; equity_sol: number }[];
}) {
  const data =
    points.length > 1
      ? points
      : [
          { ts: "", equity_sol: 1 },
          { ts: "", equity_sol: 1 },
        ];
  const vals = data.map((p) => p.equity_sol);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 0.01;
  const w = 480;
  const h = 100;
  const coords = vals.map((v, i) => {
    const x = (i / Math.max(vals.length - 1, 1)) * w;
    const y = h - ((v - min) / range) * (h - 12) - 6;
    return `${x},${y}`;
  });
  const line = coords.join(" ");
  const last = vals[vals.length - 1] ?? 0;
  const first = vals[0] ?? last;
  const deltaPct = first !== 0 ? ((last - first) / first) * 100 : 0;

  return (
    <div className="equity-strip glass">
      <header>
        <h2>Equity</h2>
        <div>
          <span className="equity-value">{last.toFixed(4)}</span>
          <span className={`equity-delta ${deltaPct >= 0 ? "up" : "down"}`}>
            {" "}
            {deltaPct >= 0 ? "+" : ""}
            {deltaPct.toFixed(2)}%
          </span>
        </div>
      </header>
      <svg viewBox={`0 0 ${w} ${h}`} className="chart-svg" preserveAspectRatio="none">
        <defs>
          <linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(176,154,208,0.35)" />
            <stop offset="100%" stopColor="rgba(176,154,208,0)" />
          </linearGradient>
          <filter id="eqGlow">
            <feGaussianBlur stdDeviation="1.5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <polygon
          points={`0,${h} ${line} ${w},${h}`}
          fill="url(#eqFill)"
        />
        <polyline
          points={line}
          fill="none"
          stroke="var(--violet)"
          strokeWidth="2"
          filter="url(#eqGlow)"
        />
      </svg>
    </div>
  );
}
