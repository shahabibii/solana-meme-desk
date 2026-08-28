import { useRef } from "react";
import { useWaveform } from "../../hooks/canvas";
import { voiceSupport } from "../../voice";

function truncPk(pk: string | null): string {
  if (!pk) return "—";
  return `${pk.slice(0, 4)}…${pk.slice(-4)}`;
}

function weightPct(v: number): number {
  // weights are typically ~0.5–1.5; map to bar 0–100
  return Math.max(4, Math.min(100, v * 50));
}

export default function Sidebar({
  equitySol,
  cashSol,
  onChainSol,
  pubkey,
  liveReady,
  mode,
  paused,
  modeBusy,
  positionsCount,
  weights,
  listening,
  voiceActive,
  onListen,
  onCommand,
  onCopyPubkey,
  fomoCopyMode,
  copyWalletCount,
  fomoFollowCount,
  copyWatchlist,
  copeReachable,
}: {
  equitySol: number;
  cashSol: number;
  onChainSol: number | null;
  pubkey: string | null;
  liveReady: boolean;
  mode: "paper" | "live";
  paused: boolean;
  modeBusy: boolean;
  positionsCount: number;
  weights: Record<string, number>;
  listening: boolean;
  voiceActive: boolean;
  onListen: () => void;
  onCommand: (cmd: string) => void;
  onCopyPubkey: () => void;
  fomoCopyMode?: boolean;
  copyWalletCount?: number;
  fomoFollowCount?: number;
  copyWatchlist?: { handle: string; wallet: string; wallet_short: string }[];
  copeReachable?: boolean | null;
}) {
  const waveRef = useRef<HTMLCanvasElement>(null);
  useWaveform(waveRef, listening || voiceActive, "#7BE8FF", 0.14);
  const canListen = voiceSupport().listen;

  const pump = weights.pump ?? 1;
  const fomo = weights.fomo ?? 1;
  const converg = weights.convergence ?? weights.converg ?? 1;
  const safety = weights.safety ?? 1;

  return (
    <div className="side" style={{ ["--i" as string]: 1 }}>
      <div className="brand">
        <svg viewBox="0 0 300 260">
          <g transform="translate(0,10)" stroke="#B09AD0" fill="none">
            <polygon
              points="150,40 240,90 240,190 150,240 60,190 60,90"
              strokeWidth="15"
              strokeLinejoin="round"
            />
            <polygon points="150,95 190,118 190,162 150,185 110,162 110,118" strokeWidth="13" />
          </g>
        </svg>
        <div>
          <div className="n">ONYX</div>
          <div className="s">COMMAND CENTER</div>
        </div>
      </div>

      <div className="nav act">
        <span className="ic">◈</span>Command Center
      </div>
      <div className="nav">
        <span className="ic">⬡</span>Agents<span className="badge">7</span>
      </div>
      <div className="nav" onClick={() => onCommand("positions")} role="button" tabIndex={0}>
        <span className="ic">◎</span>Positions
        <span className="badge">{positionsCount}</span>
      </div>
      <div className="nav" onClick={() => onCommand("trade_log")} role="button" tabIndex={0}>
        <span className="ic">≡</span>Trade Log
      </div>
      <div className="nav" onClick={() => onCommand("backtest")} role="button" tabIndex={0}>
        <span className="ic">∿</span>Backtest
      </div>
      <div className="nav" onClick={() => onCommand("learner")} role="button" tabIndex={0}>
        <span className="ic">Ψ</span>Learner
      </div>
      <div className="nav" onClick={() => onCommand("keys")} role="button" tabIndex={0}>
        <span className="ic">⚿</span>Keys
      </div>
      <div className="nav" onClick={() => onCommand("settings")} role="button" tabIndex={0}>
        <span className="ic">⚙</span>Settings
      </div>

      <div className="sidecard">
        <div className="ct">
          <i />
          Wallet
          <span className="tail" />
          <span
            className={`dot ${liveReady ? "ok" : "warn"}`}
            style={{ width: 5, height: 5 }}
          />
        </div>
        <div className="wrow">
          <span>EQUITY</span>
          <b>{equitySol.toFixed(3)} ◎</b>
        </div>
        <div className="wrow">
          <span>CASH</span>
          <b>{cashSol.toFixed(3)} ◎</b>
        </div>
        <div className="wrow">
          <span>ON-CHAIN</span>
          <b className="mut" style={{ fontSize: 10 }}>
            {onChainSol != null ? `${onChainSol.toFixed(3)} ◎` : "NOT LINKED"}
          </b>
        </div>
        <div className="wrow">
          <span>PUBKEY</span>
          <span className="cp" title="Copy" onClick={onCopyPubkey} role="button" tabIndex={0}>
            {truncPk(pubkey)} ⧉
          </span>
        </div>
      </div>

      <div className="sidecard">
        <div className="ct">
          <i />
          Learner Weights
          <span className="tail" />
        </div>
        {(
          [
            ["pump", pump],
            ["fomo", fomo],
            ["converg", converg],
            ["safety", safety],
          ] as const
        ).map(([label, v]) => (
          <div className="lwbar" key={label}>
            <span className="l">{label}</span>
            <div className="bar">
              <i style={{ width: `${weightPct(v)}%` }} />
            </div>
            {v.toFixed(2).replace(/^0/, "")}
          </div>
        ))}
      </div>

      <div className="sidecard">
        <div className="ct">
          <i />
          Desk Control
          <span className="tail" />
          {paused && <span className="dot warn" style={{ width: 5, height: 5 }} />}
        </div>
        <div className="cmds">
          {fomoCopyMode && (
            <button type="button" className="cmd" onClick={() => onCommand("fomo_sync")}>
              Sync Fomo
            </button>
          )}
          <button
            type="button"
            className="cmd live"
            disabled={modeBusy || !liveReady || fomoCopyMode}
            onClick={() => onCommand("arm_live")}
            title={
              fomoCopyMode
                ? "Fomo Copy Mode is paper-only"
                : !liveReady
                  ? "Fund live wallet first"
                  : "Arm LIVE and keep running on server"
            }
          >
            Arm LIVE & Run
          </button>
          <button
            type="button"
            className={`cmd ${paused ? "" : "stop"}`}
            disabled={modeBusy}
            onClick={() => onCommand(paused ? "resume" : "stop")}
          >
            {paused ? "Resume" : "Stop"}
          </button>
        </div>
        <p className="deskctl-hint">
          {fomoCopyMode
            ? copeReachable === false
              ? `${copyWalletCount ?? 0} wallets loaded · Cope offline`
              : `Fomo Copy · ${copyWalletCount ?? 0} wallets · paper only`
            : paused
              ? "Stopped — no new buys. Exits still run."
              : mode === "live"
                ? "Live on server — close browser anytime."
                : "Arms live + runs 24/7 on Fly."}
        </p>
      </div>

      {fomoCopyMode && (copyWatchlist?.length ?? 0) > 0 && (
        <div className="sidecard watchlist">
          <div className="ct">
            <i />
            Copy Watchlist
            <span className="tail" />
            <span className="badge">{copyWatchlist?.length ?? 0}</span>
          </div>
          {(copyWatchlist ?? []).map((w) => (
            <div className="wrow watch" key={w.wallet} title={w.wallet}>
              <span className="hdl">@{w.handle}</span>
              <span className="mut">{w.wallet_short}</span>
            </div>
          ))}
          {copeReachable === false && (
            <p className="deskctl-hint" style={{ marginTop: 6 }}>
              Manual wallets active — Sync Fomo optional while Cope is down.
            </p>
          )}
        </div>
      )}

      <div className="sidecard">
        <div className="ct">
          <i />
          Quick Commands
          <span className="tail" />
        </div>
        <div className="cmds">
          <button type="button" className="cmd" onClick={() => onCommand("status")}>
            Status
          </button>
          <button type="button" className="cmd" onClick={() => onCommand("learner")}>
            Run Learner
          </button>
          <button type="button" className="cmd" onClick={() => onCommand("backtest")}>
            Backtest
          </button>
          <button type="button" className="cmd" onClick={() => onCommand("keys")}>
            Keys
          </button>
          <button type="button" className="cmd" onClick={() => onCommand("blocks")}>
            Why Blocks?
          </button>
          <button type="button" className="cmd" onClick={() => onCommand("trade_log")}>
            Trade Log
          </button>
        </div>
      </div>

      <div className="sp" />

      <div className="voicebox">
        <div className="vt">VOICE STATUS</div>
        <canvas ref={waveRef} />
        <div
          className={`micring ${listening ? "listen" : ""}`}
          id="micring"
          onClick={onListen}
          role="button"
          tabIndex={0}
          title={canListen ? undefined : "Voice input not supported in this browser"}
        >
          <span>🎙</span>
        </div>
        <div className="vs">{listening ? "LISTENING…" : "TAP TO SPEAK"}</div>
      </div>
    </div>
  );
}
