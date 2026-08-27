import { Fragment, useEffect } from "react";
import type { AgentState } from "../store";

const ORDER = ["scout", "safety", "copy", "research", "scorer", "executor", "learner"];

export default function AgentRail({
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
        const t = setTimeout(() => onDecay(a.id), 4000);
        timers.push(t);
      }
    }
    return () => timers.forEach(clearTimeout);
  }, [agents, onDecay]);

  const sorted = ORDER.map(
    (id) => agents.find((a) => a.id === id) ?? { id, label: id, status: "idle" as const }
  );

  return (
    <aside className="agent-rail">
      <h2 className="orbitron">Pipeline</h2>
      <ul className="agent-list">
        {sorted.map((a, i) => (
          <Fragment key={a.id}>
            {i > 0 && <div className="agent-connector" aria-hidden />}
            <li
              className={`agent-card glass ${a.status}`}
              title={a.blockReasons?.join(", ") ?? undefined}
            >
              <span className="edge" aria-hidden />
              <div className="name">{a.label.toUpperCase()}</div>
              <div className="verdict">
                {a.status === "running"
                  ? "running…"
                  : a.lastVerdict
                    ? `${a.lastVerdict}${a.lastMs != null ? ` · ${a.lastMs}ms` : ""}`
                    : a.id === "learner"
                      ? "manual only"
                      : "idle"}
              </div>
            </li>
          </Fragment>
        ))}
      </ul>
    </aside>
  );
}
