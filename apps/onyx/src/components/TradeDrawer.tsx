import { useEffect, useState } from "react";
import { fetchTrades } from "../api";

type Trade = {
  id: number;
  ts: string;
  mint: string;
  symbol: string;
  side: string;
  sol: number;
  pnl_pct: number | null;
  mode: string;
  source: string;
};

export default function TradeDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [trades, setTrades] = useState<Trade[]>([]);

  useEffect(() => {
    if (!open) return;
    void fetchTrades(40).then((r) => setTrades(r.trades as Trade[]));
  }, [open]);

  if (!open) return null;

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden />
      <aside className="drawer" role="dialog" aria-label="Trade history">
        <header className="drawer-head">
          <div className="ph" style={{ padding: 0, flex: 1 }}>
            <i />
            Trade Log
            <span className="tail" />
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        {trades.length === 0 ? (
          <p className="mut" style={{ padding: "12px", fontFamily: "var(--mono)", fontSize: 11 }}>
            — no trades yet —
          </p>
        ) : (
          <ul className="drawer-list">
            {trades.map((t) => (
              <li key={t.id}>
                <time>{t.ts.slice(11, 19)}</time>
                <span>
                  {t.side.toUpperCase()} ${t.symbol} · {Number(t.sol).toFixed(3)} ◎
                  <br />
                  <span className="mut">{t.source} · {t.mode}</span>
                </span>
                <span className={t.pnl_pct != null && t.pnl_pct >= 0 ? "up" : "dn"}>
                  {t.pnl_pct != null
                    ? `${t.pnl_pct >= 0 ? "+" : ""}${t.pnl_pct.toFixed(1)}%`
                    : "—"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </>
  );
}
