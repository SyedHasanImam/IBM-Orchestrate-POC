import { useState } from "react";
import { api } from "../api/client";
import "./AgentPreviewChat.css";

type Message = { role: "user" | "assistant"; content: string };

export function AgentPreviewChat({ agentId }: { agentId: number }) {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend() {
    const question = input.trim();
    if (!question) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const data = await api.chatWithAgent(agentId, question, threadId);
      setThreadId(data.thread_id);
      setMessages((prev) => [...prev, { role: "assistant", content: data.message }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="preview-chat">
      <div className="preview-chat-window">
        {messages.length === 0 && (
          <p className="preview-chat-empty">
            Try asking this agent something — it'll answer using whatever
            Knowledge you've attached so far.
          </p>
        )}
        {messages.map((message, index) => (
          <div
            key={index}
            className={`preview-chat-bubble preview-chat-bubble-${message.role}`}
          >
            {message.content}
          </div>
        ))}
        {loading && (
          <div className="preview-chat-bubble preview-chat-bubble-assistant preview-chat-loading">
            Thinking…
          </div>
        )}
      </div>

      {error && <div className="preview-chat-error">{error}</div>}

      <div className="preview-chat-input-row">
        <input
          type="text"
          value={input}
          placeholder="Ask this agent a question…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          disabled={loading}
        />
        <button type="button" onClick={handleSend} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
