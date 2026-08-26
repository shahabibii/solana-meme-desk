export default function StatsPanel({
  stats,
  weights,
  fomoEnabled,
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
  fomoEnabled: boolean;
}) {
  if (!stats) return <p className="muted">Loading stats…</p>;
  return (
    <div className="stats-panel">
      <h2>Desk stats</h2>
      <dl>
        <div>
          <dt>Trades</dt>
          <dd>{stats.total_trades}</dd>
        </div>
        <div>
          <dt>Closed</dt>
          <dd>{stats.closed_trades}</dd>
        </div>
        <div>
          <dt>Blocks</dt>
          <dd>{stats.blocks}</dd>
        </div>
        <div>
          <dt>Win rate</dt>
          <dd>
            {stats.win_rate != null ? `${(stats.win_rate * 100).toFixed(0)}%` : "—"}
          </dd>
        </div>
        <div>
          <dt>Avg PnL</dt>
          <dd>
            {stats.avg_pnl_pct != null
              ? `${stats.avg_pnl_pct >= 0 ? "+" : ""}${stats.avg_pnl_pct.toFixed(1)}%`
              : "—"}
          </dd>
        </div>
      </dl>
      <h3>Learner weights</h3>
      <ul className="weights">
        {Object.entries(weights).map(([k, v]) => (
          <li key={k}>
            <span>{k}</span>
            <strong>{v.toFixed(2)}</strong>
          </li>
        ))}
      </ul>
      <p className="muted tiny">
        PumpPortal live · fomo {fomoEnabled ? "on" : "off — set COPE_API_KEY"}
      </p>
    </div>
  );
}
