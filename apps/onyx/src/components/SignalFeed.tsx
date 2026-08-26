import type { FeedItem } from "../store";

export default function SignalFeed({
  items,
  onSelect,
}: {
  items: FeedItem[];
  onSelect: (mint: string) => void;
}) {
  return (
    <aside className="signal-feed">
      <h2>Signal feed</h2>
      <ul>
        {items.length === 0 && (
          <li className="muted">Waiting for Pump.fun / fomo events…</li>
        )}
        {items.map((item) => (
          <li key={item.id} className={`feed-${item.kind}`}>
            <time>{new Date(item.ts).toLocaleTimeString()}</time>
            {item.mint ? (
              <button type="button" className="link" onClick={() => onSelect(item.mint!)}>
                {item.text}
              </button>
            ) : (
              <span>{item.text}</span>
            )}
          </li>
        ))}
      </ul>
    </aside>
  );
}
