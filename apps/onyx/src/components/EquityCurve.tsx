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
  const w = 400;
  const h = 80;
  const coords = vals
    .map((v, i) => {
      const x = (i / Math.max(vals.length - 1, 1)) * w;
      const y = h - ((v - min) / range) * (h - 8) - 4;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="equity-curve">
      <header>
        <h2>Equity curve</h2>
        <strong>{vals[vals.length - 1]?.toFixed(4)} SOL</strong>
      </header>
      <svg viewBox={`0 0 ${w} ${h}`} className="chart-svg">
        <polyline className="chart-line violet" points={coords} fill="none" />
      </svg>
    </div>
  );
}
