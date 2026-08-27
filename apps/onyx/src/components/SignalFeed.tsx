import type { FeedItem } from "../store";

const TAG: Record<string, string> = {
  candidate: "CANDIDATE",
  block: "BLOCKED",
  fill: "FILL",
  agent: "AGENT",
  mode: "MODE",
};

export default function SignalFeed({
  items,
  onSelect,
}: {
  items: FeedItem[];
  onSelect: (mint: string) => void;
}) {
  return (
    <aside className="signal-feed glass">
      <h2>Signal feed</h2>
      <ul>
        {items.length === 0 && (
          <li className="muted tiny">Waiting for Pump.fun / fomo events…</li>
        )}
        {items.map((item) => {
          const tag = TAG[item.kind] ?? item.kind.toUpperCase();
          return (
            <li
              key={item.id}
              className={`feed-row kind-${item.kind} ${item.mint ? "clickable" : ""}`}
              onClick={() => item.mint && onSelect(item.mint)}
            >
              <time>
                {new Date(item.ts).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </time>
              <span className={`tag ${item.kind}`}>{tag}</span>
              <span>{item.text}</span>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
