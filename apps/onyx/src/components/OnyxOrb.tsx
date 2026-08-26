export default function OnyxOrb({
  state,
  mode,
  agent,
}: {
  state: "idle" | "active" | "armed";
  mode: string;
  agent: string | null;
}) {
  return (
    <div className={`onyx-orb-wrap ${state}`}>
      <div className="orb-ring ring-1" />
      <div className="orb-ring ring-2" />
      <div className="orb-core">
        <span className="orb-glyph">◈</span>
        <p>{agent ? agent.toUpperCase() : "ONYX"}</p>
        <small>{mode} desk</small>
      </div>
      <svg className="orb-wave" viewBox="0 0 200 40" preserveAspectRatio="none">
        <path d="M0,20 Q25,5 50,20 T100,20 T150,20 T200,20" />
      </svg>
    </div>
  );
}
