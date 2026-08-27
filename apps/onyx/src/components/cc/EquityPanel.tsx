import { useMemo, useRef } from "react";
import { useEquityChart } from "../../hooks/canvas";

export default function EquityPanel({
  equitySol,
  points,
  avgPnl,
  sessionPct,
}: {
  equitySol: number;
  points: { ts: string; equity_sol: number }[];
  avgPnl: number | null;
  sessionPct: number | null;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const values = useMemo(() => {
    if (points.length >= 2) return points.map((p) => p.equity_sol);
    return [equitySol * 0.95, equitySol];
  }, [points, equitySol]);
  useEquityChart(canvasRef, values);

  const sess =
    sessionPct == null
      ? "—"
      : `${sessionPct >= 0 ? "+" : ""}${sessionPct.toFixed(1)}%`;
  const avg =
    avgPnl == null ? "—" : `${avgPnl >= 0 ? "+" : ""}${avgPnl.toFixed(1)}%`;

  return (
    <div className="p equity" style={{ ["--i" as string]: 8 }}>
      <div className="ph">
        <i />
        Equity · Session
        <span className="tail" />
      </div>
      <div className="stats">
        <div>
          <div className="k">EQUITY</div>
          <div className="v">{equitySol.toFixed(3)} ◎</div>
        </div>
        <div>
          <div className="k">SESSION</div>
          <div className={`v ${sessionPct != null && sessionPct >= 0 ? "up" : ""}`}>{sess}</div>
        </div>
        <div>
          <div className="k">AVG PNL</div>
          <div className={`v ${avgPnl != null && avgPnl >= 0 ? "up" : ""}`}>{avg}</div>
        </div>
      </div>
      <div className="eqwrap">
        <canvas ref={canvasRef} />
      </div>
    </div>
  );
}
