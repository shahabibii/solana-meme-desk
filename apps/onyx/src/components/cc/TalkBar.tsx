import { useRef, useState, type FormEvent } from "react";
import { useWaveform } from "../../hooks/canvas";
import { voiceSupport } from "../../voice";

export default function TalkBar({
  listening,
  speaking,
  muted,
  lastReply,
  onToggleListen,
  onToggleMute,
  onSend,
}: {
  listening: boolean;
  speaking: boolean;
  muted: boolean;
  lastReply: string;
  onToggleListen: () => void;
  onToggleMute: () => void;
  onSend: (text: string) => void;
}) {
  const tw1 = useRef<HTMLCanvasElement>(null);
  const tw2 = useRef<HTMLCanvasElement>(null);
  useWaveform(tw1, speaking || listening, "#E0CCF5", 0.14);
  useWaveform(tw2, speaking || listening, "#E0CCF5", 0.14);
  const [text, setText] = useState("");
  const canListen = voiceSupport().listen;

  function submit(e: FormEvent) {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;
    setText("");
    onSend(t);
  }

  return (
    <div className="talk" style={{ ["--i" as string]: 10 }}>
      <div className="tchip">
        ◎ SOL <b style={{ color: "var(--lav)" }}>—</b>
      </div>
      <div className="tchip">
        <span className="dot ok" />
        RPC —
      </div>
      <div className="dots" />
      <div
        className={`talkpill ${listening ? "listen" : ""}`}
        onClick={onToggleListen}
        role="button"
        tabIndex={0}
        title={canListen ? undefined : "Voice input not supported in this browser"}
        onKeyDown={(e) => e.key === "Enter" && onToggleListen()}
      >
        <canvas ref={tw1} />
        <div className="tt">
          <div className="a">TALK TO ONYX</div>
          <div className="b">
            {listening ? "I AM LISTENING…" : speaking ? "SPEAKING…" : "TAP TO SPEAK"}
          </div>
        </div>
        <canvas ref={tw2} />
      </div>
      <div className="dots" />
      <form className="talkin" onSubmit={submit}>
        <input
          type="text"
          placeholder="status · keys · blocks…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-label="Command input"
          title={lastReply}
        />
        <button
          type="button"
          className={`icon-btn ${muted ? "muted" : ""}`}
          title={muted ? "Unmute" : "Mute voice"}
          onClick={onToggleMute}
        >
          {muted ? "🔇" : "🔊"}
        </button>
      </form>
    </div>
  );
}
