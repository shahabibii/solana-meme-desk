import type { Position } from "../../store";

export default function OverviewPanel({
  coreLabel,
  equitySol,
  cashSol,
  connected,
  blocks,
  trades,
  winRate,
  positions,
  selectedMint,
  onSelect,
  onViewAll,
}: {
  coreLabel: string;
  equitySol: number;
  cashSol: number;
  connected: boolean;
  blocks: number;
  trades: number;
  winRate: number | null;
  positions: Position[];
  selectedMint: string | null;
  onSelect: (mint: string) => void;
  onViewAll: () => void;
}) {
  const win =
    winRate != null ? `${(winRate * 100).toFixed(0)}% WIN` : "— WIN";

  return (
    <div className="p ov" style={{ ["--i" as string]: 3 }}>
      <div className="ph">
        <i />
        Desk Overview
        <span className="tail" />
      </div>
      <div className="ovrow">
        <span className="ic">⬡</span>
        <div>
          <div className="t">Onyx Core</div>
          <div className="s">{coreLabel}</div>
        </div>
        <span className="dot cy" style={{ marginLeft: "auto" }} />
      </div>
      <div className="ovrow">
        <span className="ic">◎</span>
        <div>
          <div className="t">Equity</div>
          <div className="s">
            {equitySol.toFixed(3)} ◎ · CASH {cashSol.toFixed(3)} ◎
          </div>
        </div>
      </div>
      <div className="ovrow">
        <span className="ic">≋</span>
        <div>
          <div className="t">Stream</div>
          <div className="s">{connected ? "WS CONNECTED" : "WS RECONNECTING"}</div>
        </div>
        <span
          className={`dot ${connected ? "ok" : "warn"}`}
          style={{ marginLeft: "auto" }}
        />
      </div>
      <div className="ovrow">
        <span className="ic">Σ</span>
        <div>
          <div className="t">Session</div>
          <div className="s">
            {blocks} BLK · {trades} TRD · {win}
          </div>
        </div>
      </div>
      <div className="ph" style={{ paddingTop: 4 }}>
        <i />
        Open Positions
        <span className="tail" />
        <span className="lk" onClick={onViewAll} role="button" tabIndex={0}>
          VIEW ALL ›
        </span>
      </div>
      {positions.length === 0 ? (
        <div className="posrow" style={{ cursor: "default" }}>
          <span className="sy mut" style={{ minWidth: "auto" }}>
            Scanning PumpPortal + Safety…
          </span>
        </div>
      ) : (
        positions.slice(0, 5).map((p) => {
          const pnl = p.upnl_pct ?? 0;
          return (
            <div
              key={p.mint}
              className={`posrow ${selectedMint === p.mint ? "sel" : ""}`}
              onClick={() => onSelect(p.mint)}
              role="button"
              tabIndex={0}
            >
              <span className="sy">${p.symbol}</span>
              <span className="sr">{p.source ?? "—"}</span>
              <span className={`pn ${pnl >= 0 ? "up" : "dn"}`}>
                {pnl >= 0 ? "+" : ""}
                {pnl.toFixed(1)}%
              </span>
            </div>
          );
        })
      )}
    </div>
  );
}
