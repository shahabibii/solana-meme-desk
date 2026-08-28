import { useEffect } from "react";
import { fetchTrades } from "../api";
import { useDesk, type TradeRow } from "../store";

export default function TradeDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const trades = useDesk((s) => s.recentTrades);
  const hydrate = useDesk((s) => s.hydrateFromBoot);
  const equityPoints = useDesk((s) => s.equityPoints);

  useEffect(() => {
    if (!open) return;
    void fetchTrades(40)
      .then((r) => hydrate(r.trades as Record<string, unknown>[], equityPoints))
      .catch(() => undefined);
  }, [open, hydrate, equityPoints]);

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
            {trades.map((t: TradeRow) => (
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
