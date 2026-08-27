import { useState } from "react";
import { startListening, voiceSupport } from "../voice";

export default function ChatBar({
  lastMessage,
  onSend,
  voiceEnabled,
  onToggleVoice,
  listening,
  onListenStart,
  onListenEnd,
}: {
  lastMessage: string;
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
      <div className="chat-last">
        <strong>ONYX:</strong> {lastMessage}
      </div>
      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          const t = input.trim();
          if (!t) return;
          onSend(t);
          setInput("");
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Onyx — status, mode, keys, backtest…"
          aria-label="Chat with Onyx"
        />
        {support.listen && (
          <button
            type="button"
            className={listening ? "mic-active" : ""}
            onClick={handleVoice}
            disabled={listening}
            title="Voice command"
          >
            {listening ? "…" : "🎤"}
          </button>
        )}
        <button
          type="button"
          className={voiceEnabled ? "" : "muted-voice"}
          onClick={onToggleVoice}
          title={voiceEnabled ? "Mute" : "Unmute"}
          aria-pressed={voiceEnabled}
        >
          {voiceEnabled ? "🔊" : "🔇"}
        </button>
        <button type="submit">Send</button>
      </form>
    </footer>
  );
}
