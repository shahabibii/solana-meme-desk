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

export default function TradeHistory() {
  const [trades, setTrades] = useState<Trade[]>([]);

  useEffect(() => {
    void fetchTrades(15).then((r) => setTrades(r.trades as Trade[]));
    const iv = setInterval(() => {
      void fetchTrades(15).then((r) => setTrades(r.trades as Trade[]));
    }, 20000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="trade-history">
      <h2>Trade history</h2>
      {trades.length === 0 ? (
        <p className="muted tiny">No trades yet</p>
      ) : (
        <ul>
          {trades.map((t) => (
            <li key={t.id}>
              <time>{t.ts.slice(11, 19)}</time>
              <span className={t.side === "buy" ? "feed-fill" : "feed-candidate"}>
                {t.side} {t.symbol}
              </span>
              <span>{Number(t.sol).toFixed(3)} SOL</span>
              {t.pnl_pct != null && (
                <span className={t.pnl_pct >= 0 ? "up" : "down"}>
                  {t.pnl_pct >= 0 ? "+" : ""}
                  {t.pnl_pct.toFixed(1)}%
                </span>
              )}
              <em>{t.source}</em>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
