import type { AgentState } from "../store";

export default function AgentRail({ agents }: { agents: AgentState[] }) {
  return (
    <aside className="agent-rail">
      <h2>Agents</h2>
      <ul>
        {agents.map((a) => (
          <li key={a.id} className={`agent ${a.status}`}>
            <span className="dot" />
            <div>
              <strong>{a.label}</strong>
              <small>
                {a.status === "running"
                  ? "running…"
                  : a.lastVerdict
                    ? `${a.lastVerdict}${a.lastMs ? ` · ${a.lastMs}ms` : ""}`
                    : "idle"}
              </small>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}
