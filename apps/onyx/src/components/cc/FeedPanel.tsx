import type { FeedItem } from "../../store";

const ICON: Record<string, string> = {
  cand: "◈",
  blk: "⛔",
  fill: "◎",
  mode: "⚡",
  ag: "⬡",
  watch: "👁",
  skip: "⊘",
};

export default function FeedPanel({
  items,
  onSelect,
}: {
  items: FeedItem[];
  onSelect: (mint: string) => void;
}) {
  return (
    <div className="p feed" style={{ ["--i" as string]: 5 }}>
      <div className="ph">
        <i />
        Live Signal Feed
        <span className="tail" />
        <span className="lk">● LIVE</span>
      </div>
      <div className="feedlist">
        {items.length === 0 ? (
          <div className="fc cand">
            <div className="fi">·</div>
            <div className="fb">
              <div className="m">Awaiting signals…</div>
              <div className="sub">PumpPortal · Safety · Copy</div>
            </div>
            <span className="sev info">INFO</span>
          </div>
        ) : (
          items.map((it) => (
            <div
              key={it.id}
              className={`fc ${it.kind}`}
              onClick={() => it.mint && onSelect(it.mint)}
              role={it.mint ? "button" : undefined}
              tabIndex={it.mint ? 0 : undefined}
            >
              <div className="fi">{ICON[it.kind] ?? "·"}</div>
              <div className="fb">
                <div className="m">{it.text}</div>
                <div className="sub">{it.sub ?? it.ts.slice(11, 19)}</div>
              </div>
              <span className={`sev ${it.sev}`}>{it.sev.toUpperCase()}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
