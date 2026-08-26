import { useState } from "react";

export default function ChatBar({
  log,
  onSend,
}: {
  log: { role: string; text: string }[];
  onSend: (text: string) => void;
}) {
  const [input, setInput] = useState("");

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
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Onyx — status, mode, why blocked…"
          aria-label="Chat with Onyx"
        />
        <button type="submit">Send</button>
      </form>
    </footer>
  );
}
