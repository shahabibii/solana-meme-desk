export default function IntegrationsPanel({
  integrations,
}: {
  integrations: Record<string, { active?: boolean; ready?: boolean; hint?: string }> | null;
}) {
  if (!integrations) return null;
  const entries = Object.entries(integrations);
  return (
    <div className="integrations-panel">
      <h2>Integrations</h2>
      <ul>
        {entries.map(([key, val]) => (
          <li key={key} className={val.active ? "on" : "off"}>
            <span>{key.replace(/_/g, " ")}</span>
            <em>{val.active ? (val.ready === false ? "key set" : "on") : "off"}</em>
          </li>
        ))}
      </ul>
    </div>
  );
}
