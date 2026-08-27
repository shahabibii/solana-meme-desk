import type { Position } from "../store";

export default function PositionsPanel({
  positions,
  selectedMint,
  onSelect,
}: {
  positions: Position[];
  selectedMint: string | null;
  onSelect: (mint: string) => void;
}) {
  return (
    <div className="positions-panel glass">
      <header>
        <h2>Open</h2>
        <span className="tiny muted">{positions.length}</span>
      </header>
      {positions.length === 0 ? (
        <p className="muted tiny">Scanning PumpPortal + Safety…</p>
      ) : (
        <ul className="positions-list">
          {positions.map((p) => (
            <li
              key={p.mint}
              className={`pos-row ${selectedMint === p.mint ? "selected" : ""}`}
              onClick={() => onSelect(p.mint)}
              onKeyDown={(e) => e.key === "Enter" && onSelect(p.mint)}
              role="button"
              tabIndex={0}
            >
              <span className="sym">{p.symbol}</span>
              <code>{p.mint.slice(0, 6)}…</code>
              <span>{p.entry_sol.toFixed(3)}</span>
              <span className={p.upnl_pct != null && p.upnl_pct >= 0 ? "up" : "down"}>
                {p.upnl_pct != null
                  ? `${p.upnl_pct >= 0 ? "+" : ""}${p.upnl_pct.toFixed(1)}%`
                  : "—"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
