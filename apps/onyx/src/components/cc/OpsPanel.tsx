import type { RecentFill } from "../../store";

type IntegrationRow = {
  id: string;
  label: string;
  dot: "ok" | "warn" | "off";
  detail: string;
};

type WorkerRow = {
  status?: string;
  detail?: string | null;
  ingests?: number;
};

function truncTime(ts: string): string {
  try {
    return ts.slice(11, 16);
  } catch {
    return "—";
  }
}

function workers(
  sniperHealth: Record<string, unknown> | null | undefined,
): Record<string, WorkerRow> {
  const w = sniperHealth?.workers;
  if (!w || typeof w !== "object") return {};
  return w as Record<string, WorkerRow>;
}

function on(integrations: Record<string, { active?: boolean; ready?: boolean }> | null, key: string): boolean {
  const row = integrations?.[key];
  return Boolean(row?.active || row?.ready);
}

function resolveRows(
  integrations: Record<string, { active?: boolean; ready?: boolean }> | null,
  sniperHealth: Record<string, unknown> | null | undefined,
  fomoCopyMode: boolean,
  copyWalletCount: number,
): IntegrationRow[] {
  const w = workers(sniperHealth);
  const copyStreamOk = w.copy_stream?.status === "ok";
  const heliusWalletsOk = w.helius_wallets?.status === "ok" || on(integrations, "helius_wallets");
  const pumpKey = on(integrations, "pumpportal_key");
  const feedWorkers = ["helius_wallets", "copy_stream", "cope", "pumpportal"] as const;
  const feedsLive = feedWorkers.filter((k) => w[k]?.status === "ok").length;
  const feedsTotal = feedWorkers.length;
  const heliusIngests = w.helius_wallets?.ingests ?? 0;

  let pumpDetail = "Not linked";
  let pumpDot: IntegrationRow["dot"] = "warn";
  if (pumpKey && copyStreamOk) {
    pumpDot = "ok";
    pumpDetail = fomoCopyMode ? "Copy stream" : "Connected";
  } else if (pumpKey) {
    pumpDot = "warn";
    pumpDetail = "Key set — stream idle";
  }

  const jitoOn = on(integrations, "jito");

  return [
    {
      id: "helius",
      label: "helius",
      dot: on(integrations, "helius") ? "ok" : "warn",
      detail: on(integrations, "helius") ? "Connected" : "Not linked",
    },
    {
      id: "helius_wallets",
      label: "helius_wallets",
      dot: heliusWalletsOk ? "ok" : "warn",
      detail: heliusWalletsOk
        ? w.helius_wallets?.detail ?? `${heliusIngests} ingests`
        : "Not linked",
    },
    {
      id: "jupiter_exec",
      label: "jupiter_exec",
      dot: on(integrations, "jupiter_exec") ? "ok" : "warn",
      detail: on(integrations, "jupiter_exec") ? "Live swaps" : "No wallet",
    },
    {
      id: "solana_rpc",
      label: "solana_rpc",
      dot: on(integrations, "solana_rpc") ? "ok" : "warn",
      detail: on(integrations, "solana_rpc") ? "Connected" : "Not linked",
    },
    {
      id: "copy_trading",
      label: "copy_trading",
      dot: on(integrations, "copy_trading") ? "ok" : "warn",
      detail: on(integrations, "copy_trading")
        ? `${copyWalletCount || "—"} wallets`
        : "Not linked",
    },
    {
      id: "live_wallet",
      label: "live_wallet",
      dot: on(integrations, "live_wallet") ? "ok" : "warn",
      detail: integrations?.live_wallet?.ready ? "Connected" : "Not ready",
    },
    {
      id: "pumpportal",
      label: "pumpportal",
      dot: pumpDot,
      detail: pumpDetail,
    },
    {
      id: "jito",
      label: "jito",
      dot: jitoOn ? "ok" : "off",
      detail: jitoOn ? "Bundles on" : "Optional",
    },
    {
      id: "sniper",
      label: "sniper",
      dot: on(integrations, "sniper_ingest") ? "ok" : "off",
      detail: on(integrations, "sniper_ingest") ? "Ingest ready" : "Standby",
    },
    {
      id: "feeds",
      label: "feeds",
      dot: feedsLive > 0 ? "ok" : "warn",
      detail: feedsLive > 0 ? `${feedsLive}/${feedsTotal} live` : "No workers",
    },
  ];
}

export default function OpsPanel({
  integrations,
  sniperHealth,
  fomoCopyMode,
  copyWalletCount,
  fills,
  onViewFills,
}: {
  integrations: Record<string, { active?: boolean; ready?: boolean }> | null;
  sniperHealth?: Record<string, unknown> | null;
  fomoCopyMode?: boolean;
  copyWalletCount?: number;
  fills: RecentFill[];
  onViewFills: () => void;
}) {
  const rows = resolveRows(
    integrations,
    sniperHealth,
    Boolean(fomoCopyMode),
    copyWalletCount ?? 0,
  );

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
          {rows.map((row) => (
            <div className="ig" key={row.id}>
              <span className={`dot ${row.dot}`} />
              <div>
                <span className="n">{row.label}</span>
                <span className="s">{row.detail}</span>
              </div>
            </div>
          ))}
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
