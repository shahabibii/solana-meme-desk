export type OrbState = "idle" | "active" | "speaking" | "listening" | "armed";

const HEX_OUTER =
  "M100,22 L156,54 L156,118 L100,150 L44,118 L44,54 Z";
const HEX_MID =
  "M100,42 L136,62 L136,110 L100,130 L64,110 L64,62 Z";
const HEX_INNER =
  "M100,58 L124,72 L124,100 L100,114 L76,100 L76,72 Z";

/** Isometric cube tick lines inside outer hex */
function CubeTicks() {
  return (
    <g stroke="url(#onyxGrad)" strokeWidth="0.6" fill="none" opacity="0.7">
      <line x1="100" y1="22" x2="100" y2="86" />
      <line x1="100" y1="86" x2="44" y2="118" />
      <line x1="100" y1="86" x2="156" y2="118" />
      <line x1="44" y1="54" x2="100" y2="86" />
      <line x1="156" y1="54" x2="100" y2="86" />
      <line x1="44" y1="118" x2="156" y2="118" />
    </g>
  );
}

export default function OnyxOrb({
  state,
  statusLabel,
  onClick,
}: {
  state: OrbState;
  statusLabel: string;
  onClick: () => void;
}) {
  const armed = state === "armed" || state === "active";
  const classes = [
    "onyx-orb",
    state === "active" ? "active" : "",
    state === "speaking" ? "speaking" : "",
    state === "listening" ? "listening" : "",
    armed && state !== "speaking" && state !== "listening" ? "armed" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="orb-stage">
      <div
        className={classes}
        onClick={onClick}
        onKeyDown={(e) => e.key === "Enter" && onClick()}
        role="button"
        tabIndex={0}
        title="Talk to Onyx"
        aria-label="Talk to Onyx"
      >
        <div className="orb-breathe" aria-hidden />
        {state === "speaking" && (
          <>
            <div className="orb-ripple r1" aria-hidden />
            <div className="orb-ripple r2" aria-hidden />
          </>
        )}
        <svg className="orb-svg" viewBox="0 0 200 200" aria-hidden>
          <defs>
            <linearGradient id="onyxGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#E0CCF5" />
              <stop offset="35%" stopColor="#FFFFFF" />
              <stop offset="55%" stopColor="#B09AD0" />
              <stop offset="100%" stopColor="#7A6BA0" />
            </linearGradient>
          </defs>
          <g className="orb-spin-outer">
            <path d={HEX_OUTER} stroke="url(#onyxGrad)" strokeWidth="1.2" fill="none" />
            <CubeTicks />
          </g>
          <g className="orb-spin-mid">
            <path
              d={HEX_MID}
              stroke="url(#onyxGrad)"
              strokeWidth="1"
              fill="none"
              strokeDasharray="4 3"
            />
          </g>
          <g className="orb-spin-inner">
            <path d={HEX_INNER} stroke="url(#onyxGrad)" strokeWidth="0.9" fill="none" />
          </g>
        </svg>
      </div>
      <div className="orb-label">
        <div className="core">ONYX CORE</div>
        <div className="status">{statusLabel}</div>
      </div>
    </div>
  );
}

/** Mini SVG mark for top bar */
export function OnyxLogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      className="brand-mark"
      width={size}
      height={size}
      viewBox="0 0 200 200"
      aria-hidden
    >
      <defs>
        <linearGradient id="onyxMarkGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#E0CCF5" />
          <stop offset="50%" stopColor="#B09AD0" />
          <stop offset="100%" stopColor="#7A6BA0" />
        </linearGradient>
      </defs>
      <path d={HEX_OUTER} stroke="url(#onyxMarkGrad)" strokeWidth="3" fill="none" />
      <path d={HEX_INNER} stroke="url(#onyxMarkGrad)" strokeWidth="2" fill="none" />
    </svg>
  );
}
