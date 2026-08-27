export default function StatsPanel({
  stats,
  weights,
}: {
  stats: {
    total_trades: number;
    closed_trades: number;
    blocks: number;
    win_rate: number | null;
    avg_pnl_pct: number | null;
    total_pnl_pct: number;
  } | null;
  weights: Record<string, number>;
}) {
  const cards = [
    { label: "Trades", value: stats ? String(stats.total_trades) : "—" },
    {
      label: "Win rate",
      value:
        stats?.win_rate != null ? `${(stats.win_rate * 100).toFixed(0)}%` : "—",
    },
    { label: "Blocks", value: stats ? String(stats.blocks) : "—" },
    {
      label: "Avg PnL",
      value:
        stats?.avg_pnl_pct != null
          ? `${stats.avg_pnl_pct >= 0 ? "+" : ""}${stats.avg_pnl_pct.toFixed(1)}%`
          : "—",
    },
  ];

  const maxW = Math.max(...Object.values(weights), 1.5);

  return (
    <>
      <div className="glass" style={{ padding: "0.45rem" }}>
        <h2>Desk stats</h2>
        <div className="stats-grid">
          {cards.map((c) => (
            <div key={c.label} className="stat-card glass">
              <dt>{c.label}</dt>
              <dd>{c.value}</dd>
            </div>
          ))}
        </div>
      </div>
      <div className="glass" style={{ padding: "0.45rem" }}>
        <h2>Learner weights</h2>
        {Object.entries(weights)
          .filter(([k]) => ["pump", "fomo", "convergence", "safety", "copy"].includes(k))
          .map(([k, v]) => (
            <div key={k} className="weight-bar">
              <header>
                <span>{k}</span>
                <span>{v.toFixed(2)}</span>
              </header>
              <div className="track">
                <div className="fill" style={{ width: `${Math.min(100, (v / maxW) * 100)}%` }} />
              </div>
            </div>
          ))}
      </div>
      <div className="feeds-slot">FEEDS · not wired</div>
    </>
  );
}
