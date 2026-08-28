const KEYS = [
  "helius",
  "live_wallet",
  "copy_trading",
  "pumpportal_key",
  "jito",
  "sniper_ingest",
  "solana_rpc",
] as const;

export default function IntegrationsPanel({
  integrations,
}: {
  integrations: Record<string, { active?: boolean; ready?: boolean }> | null;
}) {
  return (
    <div className="glass" style={{ padding: "0.45rem" }}>
      <h2>Integrations</h2>
      <div className="int-grid">
        {KEYS.map((key) => {
          const val = integrations?.[key];
          const on = Boolean(val?.active);
          return (
            <div key={key} className="int-chip">
              <span className={`dot ${on ? "ok" : "warn"}`} />
              <span>{key.replace(/_/g, " ")}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
