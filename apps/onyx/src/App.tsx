import { useEffect, useMemo, useState } from "react";
import { connectOnyx, fetchMode, fetchStatus, setMode } from "./api";
import { useDesk, type FeedItem } from "./store";
import AgentRail from "./components/AgentRail";
import OnyxOrb from "./components/OnyxOrb";
import SignalFeed from "./components/SignalFeed";
import MintChart from "./components/MintChart";
import ChatBar from "./components/ChatBar";

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
  const [chatLog, setChatLog] = useState<{ role: string; text: string }[]>([
    { role: "onyx", text: "Solana meme desk online. Paper mode active — agents streaming." },
  ]);

  useEffect(() => {
    void fetchStatus().then((s) => desk.applyStatus(s));
    void fetchMode().then((m) => {
      desk.setMode(m.mode);
      desk.setLiveReady(m.live_ready);
    });
  }, []);

  useEffect(() => {
    let ws: WebSocket;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      ws = connectOnyx((data) => {
        if (data.type === "desk.status") desk.applyStatus(data);
        if (data.type === "desk.mode") desk.setMode(data.mode as "paper" | "live");
        if (data.type === "agent.start" && data.agent)
          desk.setAgentRunning(String(data.agent));
        if (data.type === "agent.done" && data.agent)
          desk.setAgentDone(String(data.agent), String(data.verdict), Number(data.ms));
        if (data.type === "mint.candidate" && data.mint)
          desk.selectMint(String(data.mint));
        if (data.type === "position.update")
          desk.pushChart(Number(data.upnl_pct ?? 50));
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
        "Switch to LIVE mode? Real SOL will be at risk once execution is wired. Continue?"
      );
      if (!ok) return;
    }
    setModeBusy(true);
    try {
      await setMode(next, next === "live");
      desk.setMode(next);
      setChatLog((l) => [...l, { role: "onyx", text: `Mode set to ${next.toUpperCase()}.` }]);
    } catch (e) {
      setModeError(e instanceof Error ? e.message : "Mode switch failed");
    } finally {
      setModeBusy(false);
    }
  }

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
            title={!desk.liveReady ? "Live needs SOLANA_PRIVATE_KEY — toggle to see setup error" : undefined}
          >
            Live
          </button>
        </div>
        <div className="wallet-pill">
          <span>{desk.mode === "paper" ? "Paper wallet" : "Live wallet"}</span>
          <strong>{desk.equitySol.toFixed(3)} SOL</strong>
          <em className={desk.connected ? "ok" : "bad"}>
            {desk.connected ? "stream live" : "reconnecting…"}
          </em>
        </div>
      </header>
      {modeError && <p className="mode-error">{modeError}</p>}

      <main className="desk-grid">
        <AgentRail agents={desk.agents} />
        <section className="center-stage">
          <MintChart points={desk.chartPoints} mint={desk.selectedMint} />
          <OnyxOrb state={orbState} mode={desk.mode} agent={desk.busyAgent} />
          <div className="positions">
            <h3>Open</h3>
            {desk.positions.length === 0 ? (
              <p className="muted">No positions — agents scanning Pump.fun & fomo…</p>
            ) : (
              <ul>
                {desk.positions.map((p) => (
                  <li key={p.mint}>
                    <strong>{p.symbol}</strong>
                    <span>{p.entry_sol.toFixed(3)} SOL</span>
                    <code>{p.mint.slice(0, 8)}…</code>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
        <SignalFeed items={desk.feed} onSelect={(m) => desk.selectMint(m)} />
      </main>

      <ChatBar
        log={chatLog}
        onSend={(text) => {
          setChatLog((l) => [...l, { role: "user", text }]);
          const lower = text.toLowerCase();
          let reply = "Monitoring agents. Ask: status, mode, last block.";
          if (lower.includes("status"))
            reply = `${desk.mode.toUpperCase()} · ${desk.equitySol.toFixed(3)} SOL · ${desk.positions.length} open · stream ${desk.connected ? "ok" : "down"}`;
          if (lower.includes("paper")) reply = "Paper mode simulates fills on the bonding curve.";
          if (lower.includes("live"))
            reply = desk.liveReady
              ? "Live path ready — toggle Live when you are armed."
              : "Live needs SOLANA_PRIVATE_KEY in orchestrator .env.";
          setChatLog((l) => [...l, { role: "onyx", text: reply }]);
        }}
      />
    </div>
  );
}
