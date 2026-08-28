import type { RecentFill } from "../../store";

const KEYS = [
  "helius",
  "pumpportal",
  "solana_rpc",
  "copy_trading",
  "live_wallet",
  "jito",
  "sniper",
  "feeds",
] as const;

function truncTime(ts: string): string {
  try {
    return ts.slice(11, 16);
  } catch {
    return "—";
  }
}

export default function OpsPanel({
  integrations,
  fills,
  onViewFills,
}: {
  integrations: Record<string, { active?: boolean; ready?: boolean }> | null;
  fills: RecentFill[];
  onViewFills: () => void;
}) {
  return (
    <div className="p ops" style={{ ["--i" as string]: 9 }}>
      <div className="ph">
        <i />
        Integrations
        <span className="tail" />
        <span className="lk" onClick={onViewFills} role="button" tabIndex={0}>
          VIEW ALL ›
        </span>
      </div>
      <div className="opsbody">
        <div className="igrid">
          {KEYS.map((k) => {
            const row = integrations?.[k];
            const ok = Boolean(row?.active || row?.ready);
            const isFeeds = k === "feeds";
            return (
              <div className="ig" key={k}>
                <span className={`dot ${isFeeds ? "off" : ok ? "ok" : "warn"}`} />
                <div>
                  <span className="n">{k}</span>
                  <span className="s">
                    {isFeeds ? "Not wired" : ok ? "Connected" : "Not linked"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
        <div className="ph" style={{ padding: "2px 0 6px" }}>
          <i />
          Recent Fills
          <span className="tail" />
        </div>
        <div>
          {fills.length === 0 ? (
            <div className="rf mut" style={{ border: "none", justifyContent: "center" }}>
              — no fills yet —
            </div>
          ) : (
            fills.map((f) => (
              <div className="rf" key={f.id}>
                <span className="sy">${f.symbol}</span>
                <span className="tm">{truncTime(f.ts)}</span>
                <span className="amt">
                  {f.side === "sell" ? "−" : "+"}
                  {Number(f.sol).toFixed(2)} ◎
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
