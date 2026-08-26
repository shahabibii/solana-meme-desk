export default function MintChart({
  points,
  mint,
}: {
  points: number[];
  mint: string | null;
}) {
  const w = 400;
  const h = 120;
  const min = Math.min(...points, 0);
  const max = Math.max(...points, 100);
  const range = max - min || 1;
  const coords = points
    .map((v, i) => {
      const x = (i / Math.max(points.length - 1, 1)) * w;
      const y = h - ((v - min) / range) * (h - 10) - 5;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="mint-chart">
      <header>
        <h2>Bonding curve</h2>
        <code>{mint ? `${mint.slice(0, 12)}…` : "— select mint —"}</code>
      </header>
      <svg viewBox={`0 0 ${w} ${h}`} className="chart-svg">
        <defs>
          <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(0, 245, 255, 0.35)" />
            <stop offset="100%" stopColor="rgba(0, 245, 255, 0)" />
          </linearGradient>
        </defs>
        <polyline className="chart-line" points={coords} fill="none" />
        <polygon
          className="chart-fill"
          points={`0,${h} ${coords} ${w},${h}`}
          fill="url(#chartGrad)"
        />
      </svg>
    </div>
  );
}
