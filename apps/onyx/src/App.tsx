import { useEffect, useMemo, useRef, useState } from "react";
import {
  chatOnyx,
  connectOnyx,
  fetchEquityCurve,
  fetchIntegrations,
  fetchMode,
  fetchStatus,
  setMode,
} from "./api";
import { useDesk, type FeedItem } from "./store";
import { speakText, loadVoiceConfig } from "./voice";
import AgentRail from "./components/AgentRail";
import OnyxOrb from "./components/OnyxOrb";
import SignalFeed from "./components/SignalFeed";
import MintChart from "./components/MintChart";
import ChatBar from "./components/ChatBar";
import EquityCurve from "./components/EquityCurve";
import StatsPanel from "./components/StatsPanel";
import IntegrationsPanel from "./components/IntegrationsPanel";
import TradeHistory from "./components/TradeHistory";
import SniperHealth from "./components/SniperHealth";

function feedFromEvent(data: Record<string, unknown>): FeedItem | null {
  const ts = String(data.ts ?? new Date().toISOString());
  const id = `${ts}-${Math.random().toString(36).slice(2, 8)}`;
  switch (data.type) {
    case "mint.candidate":
      return {
        id,
        ts,
        kind: "candidate",
        mint: String(data.mint),
        text: `New ${data.symbol} via ${data.source}`,
      };
    case "mint.blocked":
      return {
        id,
        ts,
        kind: "block",
        mint: String(data.mint),
        text: `BLOCKED — ${(data.reasons as string[])?.join(", ")}`,
      };
    case "trade.fill":
      return {
        id,
        ts,
        kind: "fill",
        mint: String(data.mint),
        text: `${data.side} ${data.sol} SOL (${data.mode})`,
      };
    case "agent.done":
      return {
        id,
        ts,
        kind: "agent",
        mint: data.mint as string | undefined,
        text: `${data.agent} → ${data.verdict} (${data.ms}ms)`,
      };
    case "desk.mode":
      return { id, ts, kind: "mode", text: `Desk mode → ${data.mode}` };
    default:
      return null;
  }
}

export default function App() {
  const desk = useDesk();
  const [modeBusy, setModeBusy] = useState(false);
  const [modeError, setModeError] = useState<string | null>(null);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const voiceRef = useRef(voiceEnabled);
  voiceRef.current = voiceEnabled;
  const lastBlockSpeak = useRef(0);
  const [listening, setListening] = useState(false);
  const [chatLog, setChatLog] = useState<{ role: string; text: string }[]>([
    { role: "onyx", text: "Solana meme desk online. Paper mode active — agents streaming." },
  ]);

  function say(text: string) {
    speakText(text, voiceRef.current);
  }

  useEffect(() => {
    void loadVoiceConfig().then((v) => {
      if (v.active) {
        setChatLog((l) => [
          ...l,
          { role: "onyx", text: `${v.label} voice online.` },
        ]);
      }
    });
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
    }, 15000);
    return () => clearInterval(iv);
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
        if (data.type === "agent.start" && data.agent)
          desk.setAgentRunning(String(data.agent));
        if (data.type === "agent.done" && data.agent)
          desk.setAgentDone(String(data.agent), String(data.verdict), Number(data.ms));
        if (data.type === "mint.candidate" && data.mint)
          desk.selectMint(String(data.mint));
        if (data.type === "position.update")
          desk.pushChart(Number(data.upnl_pct ?? 50));
        if (data.type === "trade.fill") {
          say(`${data.side} fill ${data.sol} SOL`);
        }
        // Blocks are normal on Pump.fun — don't spam voice (max once per 2 min).
        if (data.type === "mint.blocked") {
          const now = Date.now();
          if (now - lastBlockSpeak.current > 120_000) {
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
      clearTimeout(retry);
      ws?.close();
    };
  }, []);

  async function toggleMode() {
    setModeError(null);
    const next = desk.mode === "paper" ? "live" : "paper";
    if (next === "live") {
      const ok = window.confirm(
        "Switch to LIVE mode? Real SOL will be at risk. Continue?"
      );
      if (!ok) return;
    }
    setModeBusy(true);
    try {
      await setMode(next, next === "live");
      desk.setMode(next);
      const msg = `Mode set to ${next.toUpperCase()}.`;
      setChatLog((l) => [...l, { role: "onyx", text: msg }]);
      say(msg);
    } catch (e) {
      setModeError(e instanceof Error ? e.message : "Mode switch failed");
    } finally {
      setModeBusy(false);
    }
  }

  async function handleChat(text: string) {
    setChatLog((l) => [...l, { role: "user", text }]);
    try {
      const { reply } = await chatOnyx(text);
      setChatLog((l) => [...l, { role: "onyx", text: reply }]);
      say(reply);
    } catch {
      const lower = text.toLowerCase();
      let reply = "Monitoring agents. Ask: status, mode, keys, backtest.";
      if (lower.includes("status"))
        reply = `${desk.mode.toUpperCase()} · ${desk.equitySol.toFixed(3)} SOL · ${desk.positions.length} open`;
      setChatLog((l) => [...l, { role: "onyx", text: reply }]);
      say(reply);
    }
  }

  function notify(text: string) {
    setChatLog((l) => [...l, { role: "onyx", text }]);
    say(text);
  }

  const stats = desk.stats as { blocks?: number; total_trades?: number } | null;

  const orbState = useMemo(() => {
    if (desk.busyAgent) return "active";
    if (desk.mode === "live") return "armed";
    return "idle";
  }, [desk.busyAgent, desk.mode]);

  return (
    <div className="onyx-shell">
      <div className="grid-bg" aria-hidden />
      <header className="top-bar">
        <div className="brand">
          <span className="brand-mark">◈</span>
          <div>
            <h1>ONYX</h1>
            <p>Solana Meme Desk</p>
          </div>
        </div>
        <div className="mode-toggle">
          <button
            type="button"
            className={desk.mode === "paper" ? "active paper" : ""}
            onClick={() => desk.mode !== "paper" && void toggleMode()}
            disabled={modeBusy}
          >
            Paper
          </button>
          <button
            type="button"
            className={desk.mode === "live" ? "active live" : ""}
            onClick={() => desk.mode !== "live" && void toggleMode()}
            disabled={modeBusy}
            title={!desk.liveReady ? "Live needs SOLANA_PRIVATE_KEY" : undefined}
          >
            Live
          </button>
        </div>
        <div className="wallet-pill">
          <span>{desk.mode === "paper" ? "Paper wallet" : "Live wallet"}</span>
          <strong>
            {(desk.mode === "live" && desk.onChainSol != null
              ? desk.onChainSol
              : desk.equitySol
            ).toFixed(3)}{" "}
            SOL
          </strong>
          {desk.mode === "live" && desk.onChainSol != null && (
            <span className="muted tiny"> on-chain</span>
          )}
          <em className={desk.connected ? "ok" : "bad"}>
            {desk.connected ? "stream live" : "reconnecting…"}
          </em>
        </div>
      </header>
      {modeError && <p className="mode-error">{modeError}</p>}

      <VitalsStrip
        mode={desk.mode}
        connected={desk.connected}
        liveReady={desk.liveReady}
        busyAgent={desk.busyAgent}
        blocks={stats?.blocks ?? 0}
        trades={stats?.total_trades ?? 0}
        openPositions={desk.positions.length}
      />

      <main className="desk-grid">
        <AgentRail agents={desk.agents} />
        <section className="center-stage">
          <EquityCurve points={desk.equityPoints} />
          <MintChart points={desk.chartPoints} mint={desk.selectedMint} />
          <OnyxOrb state={orbState} mode={desk.mode} agent={desk.busyAgent} />
          <div className="positions">
            <h3>Open</h3>
            {desk.positions.length === 0 ? (
              <p className="muted">No positions — PumpPortal + Safety scanning…</p>
            ) : (
              <ul>
                {desk.positions.map((p) => (
                  <li key={p.mint}>
                    <strong>{p.symbol}</strong>
                    <span>{p.entry_sol.toFixed(3)} SOL</span>
                    {p.upnl_pct != null && (
                      <span className={p.upnl_pct >= 0 ? "up" : "down"}>
                        {p.upnl_pct >= 0 ? "+" : ""}
                        {p.upnl_pct.toFixed(1)}%
                      </span>
                    )}
                    <code>{p.mint.slice(0, 8)}…</code>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
        <aside className="right-col">
          <CommandDeck
            onNotify={notify}
            onRefresh={(s) => desk.applyStatus(s)}
          />
          <IntegrationsPanel integrations={desk.integrations} />
          <SniperHealth health={desk.sniperHealth as Parameters<typeof SniperHealth>[0]["health"]} />
          <TradeHistory />
          <StatsPanel
            stats={desk.stats as Parameters<typeof StatsPanel>[0]["stats"]}
            weights={desk.learnerWeights}
            fomoEnabled={desk.fomoEnabled}
          />
          <SignalFeed items={desk.feed} onSelect={(m) => desk.selectMint(m)} />
        </aside>
      </main>

      <ChatBar
        log={chatLog}
        onSend={(t) => void handleChat(t)}
        voiceEnabled={voiceEnabled}
        onToggleVoice={() => setVoiceEnabled((v) => !v)}
        listening={listening}
        onListenStart={() => setListening(true)}
        onListenEnd={() => setListening(false)}
      />
    </div>
  );
}
