import { useState } from "react";
import { startListening, voiceSupport } from "../voice";

export default function ChatBar({
  log,
  onSend,
  voiceEnabled,
  onToggleVoice,
  listening,
  onListenStart,
  onListenEnd,
}: {
  log: { role: string; text: string }[];
  onSend: (text: string) => void;
  voiceEnabled: boolean;
  onToggleVoice: () => void;
  listening: boolean;
  onListenStart: () => void;
  onListenEnd: () => void;
}) {
  const [input, setInput] = useState("");
  const support = voiceSupport();

  function handleVoice() {
    if (listening) return;
    onListenStart();
    const session = startListening({
      onFinal: (text) => {
        onSend(text);
        onListenEnd();
      },
      onError: () => onListenEnd(),
      onEnd: () => onListenEnd(),
    });
    if (!session) onListenEnd();
  }

  return (
    <footer className="chat-bar">
      <div className="chat-log">
        {log.slice(-4).map((m, i) => (
          <p key={i} className={m.role}>
            <strong>{m.role === "user" ? "You" : "Onyx"}:</strong> {m.text}
          </p>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const t = input.trim();
          if (!t) return;
          onSend(t);
          setInput("");
        }}
      >
        <button
          type="button"
          className={`voice-toggle ${voiceEnabled ? "on" : ""}`}
          onClick={onToggleVoice}
          title={
            voiceEnabled
              ? "Mute Onyx voice (Maisie)"
              : "Enable Onyx voice (Maisie)"
          }
          aria-pressed={voiceEnabled}
        >
          {voiceEnabled ? "🔊" : "🔇"}
        </button>
        {support.listen && (
          <button
            type="button"
            className={listening ? "mic active" : "mic"}
            onClick={handleVoice}
            disabled={listening}
            title="Voice command"
          >
            {listening ? "…" : "🎤"}
          </button>
        )}
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Onyx — status, mode, keys, backtest…"
          aria-label="Chat with Onyx"
        />
        <button type="submit">Send</button>
      </form>
    </footer>
  );
}
