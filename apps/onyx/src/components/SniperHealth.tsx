export default function SniperHealth({
  health,
}: {
  health: {
    overall?: string;
    workers?: Record<
      string,
      { status: string; detail?: string; ingests?: number; stale?: boolean }
    >;
  } | null;
}) {
  if (!health) return null;
  const workers = Object.entries(health.workers ?? {});
  return (
    <div className="sniper-health">
      <h2>Feeds {health.overall ? `· ${health.overall.toUpperCase()}` : ""}</h2>
      <ul>
        {workers.length === 0 ? (
          <li className="muted tiny">No worker heartbeats yet</li>
        ) : (
          workers.map(([name, w]) => (
            <li key={name} className={w.status === "ok" ? "on" : "off"}>
              <span>{name.replace(/_/g, " ")}</span>
              <em>
                {w.status}
                {w.ingests != null && w.ingests > 0 ? ` · ${w.ingests}` : ""}
                {w.stale ? " · stale" : ""}
              </em>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
