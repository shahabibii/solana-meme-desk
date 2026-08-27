import { useEffect, useState } from "react";
import type { DeskMode } from "../../store";

function truncPk(pk: string | null): string {
  if (!pk) return "—";
  return `${pk.slice(0, 4)}…${pk.slice(-4)}`;
}

export default function HeaderBar({
  connected,
  mode,
  liveReady,
  pubkey,
  modeBusy,
  onPaper,
  onLiveRequest,
  onCopyPubkey,
}: {
  connected: boolean;
  mode: DeskMode;
  liveReady: boolean;
  pubkey: string | null;
  modeBusy: boolean;
  onPaper: () => void;
  onLiveRequest: () => void;
  onCopyPubkey: () => void;
}) {
  const [clock, setClock] = useState("00:00:00");
  const [dateTxt, setDateTxt] = useState("—");

  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setClock(
        d.toLocaleTimeString("en-US", {
          hour: "numeric",
          minute: "2-digit",
          second: "2-digit",
          hour12: true,
        }),
      );
      setDateTxt(d.toDateString().toUpperCase());
    };
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, []);

  function toggleMode() {
    if (modeBusy) return;
    if (mode === "paper") onLiveRequest();
    else onPaper();
  }

  return (
    <div className="head" style={{ ["--i" as string]: 2, position: "relative" }}>
      <div className="statchip">
        <span className="dot ok" />
        SYSTEM STATUS <b>● OPTIMAL</b>
      </div>
      <div className="statchip">
        <span className={`dot ${connected ? "ok" : "warn"}`} />
        STREAM{" "}
        <b style={{ color: connected ? "var(--cyan)" : "var(--amber)" }}>
          {connected ? "CONNECTED" : "RECONNECTING"}
        </b>
      </div>
      <div className="clockwrap">
        <div className="d">{dateTxt}</div>
        <div className="c">{clock}</div>
      </div>
      <div className="sp" />
      <div
        className={`mode-toggle ${mode === "live" ? "live" : ""}`}
        onClick={toggleMode}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && toggleMode()}
      >
        <span className={mode === "paper" ? "on" : ""}>PAPER</span>
        <span className={mode === "live" ? "on" : ""}>LIVE</span>
      </div>
      <div className="statchip">
        <span className={`dot ${liveReady && mode === "live" ? "ok" : "warn"}`} />
        <span>
          {mode === "live" && liveReady
            ? "LIVE-ARMED"
            : liveReady
              ? "WALLET READY"
              : "WALLET NOT READY"}
        </span>
      </div>
      <div
        className="op"
        onClick={onCopyPubkey}
        role="button"
        tabIndex={0}
        title="Copy pubkey"
        style={{ cursor: "pointer" }}
      >
        <div className="av">OP</div>
        <div>
          <div className="nm">Operator</div>
          <div className="rl">{truncPk(pubkey)}</div>
        </div>
      </div>
    </div>
  );
}
