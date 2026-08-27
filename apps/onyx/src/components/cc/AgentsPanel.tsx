import { useEffect, useRef } from "react";
import { AGENT_DECAY_MS } from "../../config";
import { useAgentWave } from "../../hooks/canvas";
import type { AgentState } from "../../store";

const ORDER = ["scout", "safety", "copy", "research", "scorer", "executor", "learner"];

function AgentRow({ agent, index }: { agent: AgentState; index: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useAgentWave(canvasRef, agent.status === "running", index);

  const verdict =
    agent.status === "running"
      ? "run…"
      : agent.lastVerdict
        ? agent.lastVerdict.length > 8
          ? agent.lastVerdict.slice(0, 7)
          : agent.lastVerdict
        : agent.id === "learner"
          ? "manual"
          : "idle";

  const dot =
    agent.status === "running"
      ? "cy"
      : agent.status === "pass"
        ? "ok"
        : agent.status === "block"
          ? "warn"
          : agent.status === "trade"
            ? "ok"
            : "off";

  return (
    <div className={`ag ${agent.status !== "idle" ? agent.status : ""}`}>
      <span className={`dot ${dot}`} />
      <span className="nm">{agent.label.toUpperCase()}</span>
      <canvas ref={canvasRef} />
      <span className="vd">{verdict}</span>
    </div>
  );
}

export default function AgentsPanel({
  agents,
  onDecay,
}: {
  agents: AgentState[];
  onDecay: (id: string) => void;
}) {
  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    for (const a of agents) {
      if (a.status !== "idle" && a.status !== "running" && a.lastVerdict) {
        timers.push(setTimeout(() => onDecay(a.id), AGENT_DECAY_MS));
      }
    }
    return () => timers.forEach(clearTimeout);
  }, [agents, onDecay]);

  const sorted = ORDER.map(
    (id) => agents.find((a) => a.id === id) ?? { id, label: id, status: "idle" as const }
  );

  return (
    <div className="p agents" style={{ ["--i" as string]: 6 }}>
      <div className="ph">
        <i />
        Active Agents
        <span className="tail" />
        <span className="lk">7 LINKED</span>
      </div>
      <div className="aggrid">
        {sorted.map((a, i) => (
          <AgentRow key={a.id} agent={a} index={i} />
        ))}
      </div>
    </div>
  );
}
