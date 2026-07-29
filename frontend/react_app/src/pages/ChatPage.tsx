import { useState } from "react";
import { api } from "../api/client";
import "./ChatPage.css";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  routedTo?: string | null;
};

export function ChatPage() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
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
      const data = await api.chat(question, threadId);
      setThreadId(data.thread_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.message, routedTo: data.routed_to },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function handleNewConversation() {
    setThreadId(null);
    setMessages([]);
    setError(null);
  }

  return (
    <div className="chat-page">
      <h1>Ask a Question</h1>
      <p className="chat-subtitle">
        Ad hoc questions get routed to one specialist agent directly — this
        never runs the full report-generation pipeline.
      </p>

      <div className="chat-window">
        {messages.length === 0 && (
          <p className="chat-empty">Ask about the fund's holdings or compliance status.</p>
        )}
        {messages.map((message, index) => (
          <div key={index} className={`chat-bubble chat-bubble-${message.role}`}>
            <div className="chat-bubble-content">{message.content}</div>
            {message.routedTo && (
              <div className="chat-routed-to">Routed to: {message.routedTo}</div>
            )}
          </div>
        ))}
        {loading && (
          <div className="chat-bubble chat-bubble-assistant chat-loading">Thinking…</div>
        )}
      </div>

      {error && <div className="chat-error">{error}</div>}

      <div className="chat-input-row">
        <input
          type="text"
          value={input}
          placeholder="Ask about holdings or compliance..."
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

      {messages.length > 0 && (
        <button type="button" className="chat-reset" onClick={handleNewConversation}>
          Start a new conversation
        </button>
      )}
    </div>
  );
}
