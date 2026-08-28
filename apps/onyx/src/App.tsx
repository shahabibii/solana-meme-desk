import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  chatOnyx,
  connectOnyx,
  fetchEquityCurve,
  fetchIntegrations,
  fetchMode,
  fetchStatus,
  runBacktest,
  runLearner,
  setMode,
  armLiveDesk,
  stopDesk,
  resumeDesk,
  bootstrapFomoCopy,
} from "./api";
import { BLOCK_SPEAK_THROTTLE_MS, POLL_MS } from "./config";
import { useDesk, type FeedItem } from "./store";
import { speakText, loadVoiceConfig, startListening, unlockAudio, voiceSupport } from "./voice";
import {
  applyMotionClass,
  getMotionPref,
  motionEnabled,
  osPrefersReducedMotion,
  setMotionPref,
} from "./motion";
import BootSequence from "./components/BootSequence";
import AgentsPanel from "./components/cc/AgentsPanel";
import CorePanel from "./components/cc/CorePanel";
import EquityPanel from "./components/cc/EquityPanel";
import FeedPanel from "./components/cc/FeedPanel";
import HeaderBar from "./components/cc/HeaderBar";
import MonitorPanel from "./components/cc/MonitorPanel";
import OpsPanel from "./components/cc/OpsPanel";
import OverviewPanel from "./components/cc/OverviewPanel";
import Sidebar from "./components/cc/Sidebar";
import TalkBar from "./components/cc/TalkBar";
import TradeDrawer from "./components/TradeDrawer";
import { useStarfield } from "./hooks/canvas";

function feedFromEvent(data: Record<string, unknown>): FeedItem | null {
  const ts = String(data.ts ?? new Date().toISOString());
  const id = `${ts}-${Math.random().toString(36).slice(2, 8)}`;
  switch (data.type) {
    case "mint.candidate":
      return {
        id,
        ts,
        kind: "cand",
        sev: "info",
        mint: String(data.mint),
        text: `${data.symbol} candidate via ${data.source}`,
        sub: String(data.mint).slice(0, 8) + "…",
      };
    case "mint.blocked":
      return {
        id,
        ts,
        kind: "blk",
        sev: "warn",
        mint: String(data.mint),
        text: `${data.symbol ?? "mint"} blocked`,
        sub: (data.reasons as string[])?.join(", ") ?? "safety",
      };
    case "trade.fill":
      return {
        id,
        ts,
        kind: "fill",
        sev: "live",
        mint: String(data.mint),
        text: `${String(data.side).toUpperCase()} ${data.symbol ?? ""} ${data.sol} ◎`,
        sub: `${data.mode} · pumpportal`,
      };
    case "agent.done":
      return {
        id,
        ts,
        kind: "ag",
        sev: "info",
        mint: data.mint as string | undefined,
        text: `${data.agent} → ${data.verdict}`,
        sub: `${data.ms}ms`,
      };
    case "desk.mode":
      return {
        id,
        ts,
        kind: "mode",
        sev: "mode",
        text: `Mode → ${String(data.mode).toUpperCase()}`,
        sub: "desk.mode",
      };
    default:
      return null;
  }
}

function readMute(): boolean {
  try {
    return localStorage.getItem("onyx_mute") === "1";
  } catch {
    return false;
  }
}

export default function App() {
  const desk = useDesk();
  const starsRef = useRef<HTMLCanvasElement>(null);
  useStarfield(starsRef);

  const [booted, setBooted] = useState(false);
  const [modeBusy, setModeBusy] = useState(false);
  const [modeError, setModeError] = useState<string | null>(null);
  const [muted, setMuted] = useState(readMute);
  const mutedRef = useRef(muted);
  mutedRef.current = muted;
  const lastBlockSpeak = useRef(0);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [liveConfirm, setLiveConfirm] = useState(false);
  const [tradeDrawer, setTradeDrawer] = useState(false);
  const [backtestModal, setBacktestModal] = useState<Record<string, unknown> | null>(null);
  const [lastReply, setLastReply] = useState("Solana meme desk online — agents streaming.");
  const listenSession = useRef<{ stop: () => void } | null>(null);
  const [showMotionBanner, setShowMotionBanner] = useState(false);

  const onBootDone = useCallback(() => setBooted(true), []);

  useEffect(() => {
    applyMotionClass();
    // Windows Animation Effects Off → prefers-reduced-motion; offer override once.
    if (osPrefersReducedMotion() && getMotionPref() === "auto" && !motionEnabled()) {
      setShowMotionBanner(true);
    }
  }, []);

  function enableDeskMotion() {
    unlockAudio();
    setMotionPref("on");
    setShowMotionBanner(false);
  }

  function say(text: string) {
    speakText(text, !mutedRef.current, {
      onStart: () => setSpeaking(true),
      onEnd: () => setSpeaking(false),
    });
  }

  const decayAgent = useCallback((id: string) => desk.decayAgent(id), [desk]);

  useEffect(() => {
    void loadVoiceConfig();
    void fetchStatus().then((s) => desk.applyStatus(s));
    void fetchMode().then((m) => {
      desk.setMode(m.mode);
      desk.setLiveReady(m.live_ready);
    });
    void fetchIntegrations().then((i) =>
      desk.applyStatus({ integrations: i.integrations })
    );
    void fetchEquityCurve().then((c) => desk.setEquityPoints(c.points ?? []));
    const iv = setInterval(() => {
      void fetchEquityCurve().then((c) => desk.setEquityPoints(c.points ?? []));
      void fetchStatus().then((s) => desk.applyStatus(s));
      void fetchMode().then((m) => {
        desk.setMode(m.mode);
        desk.setLiveReady(m.live_ready);
      });
    }, POLL_MS);
    return () => clearInterval(iv);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let ws: WebSocket;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      ws = connectOnyx((data) => {
        if (data.type === "desk.status") desk.applyStatus(data);
        if (data.type === "desk.mode") {
          desk.setMode(data.mode as "paper" | "live");
          say(`Desk mode ${data.mode}`);
        }
        if (data.type === "agent.start" && data.agent) {
          desk.setAgentRunning(String(data.agent));
          desk.setLastScore(null);
        }
        if (data.type === "agent.done" && data.agent) {
          const agent = String(data.agent);
          const verdict = String(data.verdict);
          desk.setAgentDone(
            agent,
            verdict,
            Number(data.ms),
            data.reasons as string[] | undefined
          );
          if (agent === "scorer" && data.score != null) {
            desk.setLastScore(Number(data.score));
          } else if (agent === "scorer" && /TRD|SKIP|TRADE/i.test(verdict)) {
            const m = verdict.match(/(\d+)/);
            if (m) desk.setLastScore(Number(m[1]));
          }
        }
        if (data.type === "mint.candidate" && data.mint)
          desk.selectMint(String(data.mint));
        if (data.type === "position.update") {
          desk.pushChart(Number(data.upnl_pct ?? 0));
          if (data.mint) desk.selectMint(String(data.mint));
        }
        if (data.type === "trade.fill") {
          say(`${data.side} fill ${data.sol} SOL`);
          desk.pushFill({
            id: `${data.ts ?? Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            symbol: String(data.symbol ?? "???"),
            sol: Number(data.sol ?? 0),
            side: String(data.side ?? "buy"),
            ts: String(data.ts ?? new Date().toISOString()),
          });
          void fetchEquityCurve().then((c) => desk.setEquityPoints(c.points ?? []));
          void fetchStatus().then((s) => desk.applyStatus(s));
        }
        if (data.type === "mint.blocked") {
          const now = Date.now();
          if (now - lastBlockSpeak.current > BLOCK_SPEAK_THROTTLE_MS) {
            lastBlockSpeak.current = now;
            say("Safety filtering launches — blocks are normal on Pump.fun.");
          }
        }
        const item = feedFromEvent(data);
        if (item) desk.pushFeed(item);
      });
      ws.onopen = () => desk.setConnected(true);
      ws.onclose = () => {
        desk.setConnected(false);
        retry = setTimeout(connect, 2000);
      };
    };
    connect();
    return () => {
      clearTimeout(retry!);
      ws?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function armLiveAndRun() {
    setModeError(null);
    if (!desk.liveReady) {
      setModeError("WALLET NOT READY");
      notify("Wallet not ready — fund your live wallet first.");
      return;
    }
    if (desk.mode === "live" && !desk.paused) {
      notify("Already LIVE and running. Close the browser anytime.");
      return;
    }
    if (desk.mode === "live" && desk.paused) {
      setModeBusy(true);
      try {
        const r = await resumeDesk();
        desk.applyStatus(await fetchStatus());
        notify(r.message);
      } catch (e) {
        setModeError(e instanceof Error ? e.message : "Resume failed");
      } finally {
        setModeBusy(false);
      }
      return;
    }
    setLiveConfirm(true);
  }

  async function confirmArmLive() {
    setModeError(null);
    setModeBusy(true);
    try {
      const r = await armLiveDesk();
      desk.setMode(r.mode);
      desk.applyStatus(await fetchStatus());
      setLastReply(r.message);
      say(r.message);
    } catch (e) {
      setModeError(e instanceof Error ? e.message : "Arm LIVE failed");
    } finally {
      setModeBusy(false);
      setLiveConfirm(false);
    }
  }

  async function stopTrading() {
    setModeBusy(true);
    try {
      const r = await stopDesk();
      desk.applyStatus(await fetchStatus());
      notify(r.message);
    } catch (e) {
      notify(e instanceof Error ? e.message : "Stop failed");
    } finally {
      setModeBusy(false);
    }
  }

  async function resumeTrading() {
    setModeBusy(true);
    try {
      const r = await resumeDesk();
      desk.applyStatus(await fetchStatus());
      notify(r.message);
    } catch (e) {
      notify(e instanceof Error ? e.message : "Resume failed");
    } finally {
      setModeBusy(false);
    }
  }

  async function applyMode(next: "paper" | "live") {
    setModeError(null);
    if (next === "live" && !desk.liveReady) {
      setModeError("WALLET NOT READY");
      setLiveConfirm(false);
      setLastReply("Wallet not ready — keep paper mode.");
      say("Wallet not ready.");
      return;
    }
    setModeBusy(true);
    try {
      await setMode(next, next === "live");
      desk.setMode(next);
      const msg = next === "live" ? "Live mode armed." : "Paper mode restored.";
      setLastReply(msg);
      say(msg);
    } catch (e) {
      setModeError(e instanceof Error ? e.message : "Mode switch failed");
    } finally {
      setModeBusy(false);
      setLiveConfirm(false);
    }
  }

  async function handleChat(text: string) {
    unlockAudio();
    setLastReply("…");
    try {
      const { reply } = await chatOnyx(text);
      setLastReply(reply);
      say(reply);
    } catch {
      const reply = `${desk.mode.toUpperCase()} · ${desk.equitySol.toFixed(3)} SOL · ${desk.positions.length} open`;
      setLastReply(reply);
      say(reply);
    }
  }

  function notify(text: string) {
    setLastReply(text);
    say(text);
  }

  function toggleListen() {
    unlockAudio();
    if (!voiceSupport().listen) return;
    if (listening) {
      listenSession.current?.stop();
      setListening(false);
      return;
    }
    setListening(true);
    listenSession.current = startListening({
      onFinal: (t) => {
        void handleChat(t);
        setListening(false);
      },
      onError: () => setListening(false),
      onEnd: () => setListening(false),
    });
    if (!listenSession.current) setListening(false);
  }

  function toggleMute() {
    unlockAudio();
    setMuted((m) => {
      const next = !m;
      try {
        localStorage.setItem("onyx_mute", next ? "1" : "0");
      } catch {
        /* ignore */
      }
      // Unmuting should be obvious; speak a short cue once audio is unlocked.
      if (!next) {
        speakText("Voice on.", true, {
          onStart: () => setSpeaking(true),
          onEnd: () => setSpeaking(false),
        });
      }
      return next;
    });
  }

  async function runCommand(cmd: string) {
    switch (cmd) {
      case "trade_log":
      case "positions":
        setTradeDrawer(true);
        return;
      case "settings":
        notify("Settings panel coming soon.");
        return;
      case "status": {
        const s = await fetchStatus();
        desk.applyStatus(s);
        const st = s.stats as { blocks?: number; total_trades?: number } | undefined;
        const w = s.wallet as { open_positions?: number; equity_sol?: number } | undefined;
        notify(
          `${String(s.mode).toUpperCase()} · ${Number(w?.equity_sol ?? 0).toFixed(3)} SOL · ${w?.open_positions ?? 0} open · ${st?.blocks ?? 0} blocks`
        );
        return;
      }
      case "learner": {
        const r = await runLearner();
        desk.applyStatus(await fetchStatus());
        notify(
          `Learner: ${Object.entries(r.weights)
            .map(([k, v]) => `${k}=${v.toFixed(2)}`)
            .join(", ")}`
        );
        return;
      }
      case "backtest": {
        const r = await runBacktest();
        setBacktestModal(r);
        const n = Number(r.round_trips ?? 0);
        notify(
          n
            ? `Backtest: ${n} RT, win ${(Number(r.win_rate ?? 0) * 100).toFixed(0)}%`
            : String(r.message ?? "No closed trades yet")
        );
        return;
      }
      case "keys": {
        const i = await fetchIntegrations();
        desk.applyStatus({ integrations: i.integrations });
        const active = Object.entries(i.integrations)
          .filter(([, v]) => v.active)
          .map(([k]) => k);
        notify(`Active: ${active.join(", ") || "RPC only"}`);
        return;
      }
      case "blocks": {
        const { reply } = await chatOnyx("blocks");
        notify(reply);
        return;
      }
      case "arm_live":
        await armLiveAndRun();
        return;
      case "stop":
        await stopTrading();
        return;
      case "resume":
        await resumeTrading();
        return;
      case "fomo_sync": {
        setModeBusy(true);
        try {
          const r = await bootstrapFomoCopy();
          desk.applyStatus(await fetchStatus());
          const walletCount = Number(r.wallets ?? desk.copyWalletCount ?? 0);
          notify(`${walletCount} wallets in watchlist`);
        } catch (e) {
          notify(e instanceof Error ? e.message : "Refresh failed");
        } finally {
          setModeBusy(false);
        }
        return;
      }
      default:
        void handleChat(cmd);
    }
  }

  const stats = desk.stats as {
    blocks?: number;
    total_trades?: number;
    win_rate?: number | null;
    avg_pnl_pct?: number | null;
    closed_trades?: number;
    total_pnl_pct?: number;
  } | null;

  const exposure = useMemo(() => {
    if (desk.equitySol <= 0) return 0;
    const used = Math.max(0, desk.equitySol - desk.cashSol);
    return Math.min(100, (used / desk.equitySol) * 100);
  }, [desk.equitySol, desk.cashSol]);

  const sessionPct = useMemo(() => {
    if (typeof stats?.total_pnl_pct === "number") return stats.total_pnl_pct;
    return null;
  }, [stats]);

  const coreLabel = desk.fomoCopyMode
    ? desk.busyAgent
      ? `FOMO COPY · ${desk.busyAgent.toUpperCase()}`
      : "FOMO COPY · SCANNING SMART MONEY"
    : desk.busyAgent
      ? `ACTIVE · EVALUATING ${desk.busyAgent.toUpperCase()}`
      : "ACTIVE · SCANNING";

  const copyPubkey = () => {
    if (desk.walletPubkey) {
      void navigator.clipboard.writeText(desk.walletPubkey);
      notify("Pubkey copied.");
    }
  };

  return (
    <>
      <canvas id="stars" ref={starsRef} />
      <div className="scan" aria-hidden />
      {!booted && <BootSequence onDone={onBootDone} />}

      <div className={`frame ${booted ? "on" : ""}`} id="frame">
        <Sidebar
          equitySol={desk.equitySol}
          cashSol={desk.cashSol}
          onChainSol={desk.onChainSol}
          pubkey={desk.walletPubkey}
          liveReady={desk.liveReady}
          mode={desk.mode}
          paused={desk.paused}
          modeBusy={modeBusy}
          positionsCount={desk.positions.length}
          weights={desk.learnerWeights}
          listening={listening}
          voiceActive={speaking}
          onListen={toggleListen}
          onCommand={(c) => void runCommand(c)}
          onCopyPubkey={copyPubkey}
          fomoCopyMode={desk.fomoCopyMode}
          copyWalletCount={desk.copyWalletCount}
          copyWatchlist={desk.copyWatchlist}
        />

        <HeaderBar
          connected={desk.connected}
          mode={desk.mode}
          liveReady={desk.liveReady}
          paused={desk.paused}
          pubkey={desk.walletPubkey}
          modeBusy={modeBusy}
          onPaper={() => void applyMode("paper")}
          onLiveRequest={() => void armLiveAndRun()}
          onStop={() => void stopTrading()}
          onCopyPubkey={copyPubkey}
          fomoCopyMode={desk.fomoCopyMode}
        />

        <div className="main" style={{ ["--i" as string]: 0 }}>
          <div className="grid">
            <OverviewPanel
              coreLabel={coreLabel}
              equitySol={desk.equitySol}
              cashSol={desk.cashSol}
              connected={desk.connected}
              blocks={stats?.blocks ?? 0}
              trades={stats?.total_trades ?? 0}
              winRate={stats?.win_rate ?? null}
              positions={desk.positions}
              selectedMint={desk.selectedMint}
              onSelect={(m) => desk.selectMint(m)}
              onViewAll={() => setTradeDrawer(true)}
            />
            <CorePanel
              active={Boolean(desk.busyAgent)}
              speaking={speaking}
              armed={desk.mode === "live"}
              mode={desk.mode}
              busyAgent={desk.busyAgent}
              lastScore={desk.lastScore}
            />
            <FeedPanel items={desk.feed} onSelect={(m) => desk.selectMint(m)} />
            <AgentsPanel agents={desk.agents} onDecay={decayAgent} />
            <MonitorPanel
              winRate={stats?.win_rate ?? null}
              exposure={exposure}
              safetyW={desk.learnerWeights.safety ?? 1}
              trades={stats?.total_trades ?? 0}
              blocks={stats?.blocks ?? 0}
              avgPnl={stats?.avg_pnl_pct ?? null}
            />
            <EquityPanel
              equitySol={desk.equitySol}
              points={desk.equityPoints}
              avgPnl={stats?.avg_pnl_pct ?? null}
              sessionPct={sessionPct}
            />
            <OpsPanel
              integrations={desk.integrations}
              sniperHealth={desk.sniperHealth}
              fomoCopyMode={desk.fomoCopyMode}
              copyWalletCount={desk.copyWalletCount}
              fills={desk.recentFills}
              onViewFills={() => setTradeDrawer(true)}
            />
          </div>
        </div>

        <TalkBar
          listening={listening}
          speaking={speaking}
          muted={muted}
          lastReply={lastReply}
          onToggleListen={toggleListen}
          onToggleMute={toggleMute}
          onSend={(t) => void handleChat(t)}
        />
      </div>

      {modeError && (
        <p className="mode-banner" role="alert">
          {modeError}
        </p>
      )}

      {liveConfirm && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal p" role="dialog" aria-labelledby="live-title">
            <div className="ph">
              <i />
              Confirm Live
              <span className="tail" />
            </div>
            <h2 id="live-title">Arm LIVE &amp; run?</h2>
            <p>
              {desk.fomoCopyMode
                ? `Real SOL copy-trades from your ${desk.copyWalletCount} watched wallets (max 0.07 ◎ per position). The desk keeps running on the server — you can close this browser.`
                : "Real PumpPortal orders with your wallet. The desk keeps running on the server — you can close this browser."}
            </p>
            <div className="modal-actions">
              <button type="button" className="cmd" onClick={() => setLiveConfirm(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="cmd primary"
                onClick={() => void confirmArmLive()}
                disabled={modeBusy}
              >
                Arm LIVE &amp; Run
              </button>
            </div>
          </div>
        </div>
      )}

      {backtestModal && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => setBacktestModal(null)}
        >
          <div
            className="modal p"
            role="dialog"
            onClick={(e) => e.stopPropagation()}
            aria-labelledby="bt-title"
          >
            <div className="ph">
              <i />
              Backtest
              <span className="tail" />
            </div>
            <h2 id="bt-title">Results</h2>
            <p className="bt-body">
              Round-trips: {String(backtestModal.round_trips ?? "—")}
              <br />
              Win rate:{" "}
              {backtestModal.win_rate != null
                ? `${(Number(backtestModal.win_rate) * 100).toFixed(0)}%`
                : "—"}
              <br />
              Sharpe: {String(backtestModal.sharpe ?? "—")}
              <br />
              {backtestModal.by_source
                ? `By source: ${JSON.stringify(backtestModal.by_source)}`
                : String(backtestModal.message ?? "")}
            </p>
            <div className="modal-actions">
              <button type="button" className="cmd primary" onClick={() => setBacktestModal(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {showMotionBanner && (
        <div className="motion-banner" role="status">
          <p>
            Windows has animations off, so the desk looks frozen. Enable motion for the
            sphere + logo (saved on this PC).
          </p>
          <button type="button" className="cmd primary" onClick={enableDeskMotion}>
            Enable motion
          </button>
          <button
            type="button"
            className="cmd"
            onClick={() => {
              setMotionPref("off");
              setShowMotionBanner(false);
            }}
          >
            Keep still
          </button>
        </div>
      )}

      <TradeDrawer open={tradeDrawer} onClose={() => setTradeDrawer(false)} />
    </>
  );
}
