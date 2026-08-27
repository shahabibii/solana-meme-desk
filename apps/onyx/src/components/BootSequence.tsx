import { useEffect, useState } from "react";
import { motionEnabled } from "../motion";

const LINES = [
  "INITIALIZING ONYX CORE",
  "LINKING HELIUS + PUMPPORTAL",
  "AGENT PIPELINE ▸ 7/7",
  "COMMAND CENTER ONLINE",
];

export default function BootSequence({ onDone }: { onDone: () => void }) {
  const [txt, setTxt] = useState(LINES[0]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!motionEnabled()) {
      setDone(true);
      onDone();
      return;
    }
    let bi = 0;
    const iv = setInterval(() => {
      bi += 1;
      if (bi >= LINES.length) {
        clearInterval(iv);
        setTimeout(() => {
          setDone(true);
          onDone();
        }, 380);
      } else {
        setTxt(LINES[bi]);
      }
    }, 430);
    return () => clearInterval(iv);
  }, [onDone]);

  function skip() {
    setDone(true);
    onDone();
  }

  return (
    <div
      id="boot"
      className={done ? "done" : ""}
      onClick={skip}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && skip()}
    >
      <svg viewBox="0 0 300 260">
        <g transform="translate(0,10)" stroke="#B09AD0" fill="none">
          <polygon
            className="b1"
            points="150,40 240,90 240,190 150,240 60,190 60,90"
            strokeWidth="4"
            strokeLinejoin="round"
          />
          <polygon
            className="b2"
            points="150,70 210,105 210,175 150,210 90,175 90,105"
            strokeWidth="1.5"
          />
          <polygon
            className="b3"
            points="150,95 190,118 190,162 150,185 110,162 110,118"
            strokeWidth="3"
          />
        </g>
      </svg>
      <div id="bootTxt">{txt}</div>
    </div>
  );
}
