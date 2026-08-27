import { useRef } from "react";
import { useSphere } from "../../hooks/canvas";
import JarvisLogo from "../JarvisLogo";
import type { DeskMode } from "../../store";

export default function CorePanel({
  active,
  speaking,
  armed,
  mode,
  busyAgent,
  lastScore,
}: {
  active: boolean;
  speaking: boolean;
  armed: boolean;
  mode: DeskMode;
  busyAgent: string | null;
  lastScore: number | null;
}) {
  const sphereRef = useRef<HTMLCanvasElement>(null);
  useSphere(sphereRef, active);

  const cls = ["p", "core", active && "active", speaking && "speaking", armed && "armed"]
    .filter(Boolean)
    .join(" ");

  const scoreTxt = lastScore != null ? `${lastScore} / 72` : "— / 72";
  const scoreColor = lastScore != null && lastScore >= 72 ? "var(--green)" : "var(--cyan)";

  return (
    <div className={cls} style={{ ["--i" as string]: 4 }}>
      <div className="ph">
        <i />
        Onyx AI Core
        <span className="tail" />
        <span className="lk">{active ? "EVALUATING" : "IDLE"}</span>
      </div>
      <div className="corestage">
        <canvas id="sphere" ref={sphereRef} />
        <div className="ripple" />
        <div className="ripple" />
        <div className="coremid">
          <JarvisLogo />
          <div className="t1">ONYX</div>
          <div className="t2">{armed ? "LIVE ARMED" : "AI TRADING CORE"}</div>
          <div className="t3">v3.0.0 · 7 AGENTS LINKED</div>
        </div>
        <div className="corehud">
          <div className="chip">
            SCORE ▸ <b style={{ color: scoreColor }}>{scoreTxt}</b>
          </div>
          <div className="chip">
            AGENT ▸ <b>{busyAgent ? busyAgent.toUpperCase() : "IDLE"}</b>
          </div>
          <div className="chip">
            MODE ▸{" "}
            <b style={{ color: mode === "live" ? "var(--amber)" : "var(--blue)" }}>
              {mode.toUpperCase()}
            </b>
          </div>
        </div>
      </div>
    </div>
  );
}
