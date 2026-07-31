import { ArrowUp } from "lucide-react";
import { api } from "../api/client";
import { getAgentChat, updateAgentChat, useAgentChat } from "../state/agentChatHistory";
import { Markdown } from "./ui/Markdown";
import "./AgentPreviewChat.css";

export function AgentPreviewChat({ agentId }: { agentId: number }) {
  const { threadId, messages, input, loading, error } = useAgentChat(agentId);

  async function handleSend() {
    const question = input.trim();
    if (!question) return;

    updateAgentChat(agentId, {
      messages: [...getAgentChat(agentId).messages, { role: "user", content: question }],
      input: "",
      loading: true,
      error: null,
    });

    try {
      const data = await api.chatWithAgent(agentId, question, threadId);
      updateAgentChat(agentId, {
        threadId: data.thread_id,
        messages: [
          ...getAgentChat(agentId).messages,
          { role: "assistant", content: data.message },
        ],
      });
    } catch (err) {
      updateAgentChat(agentId, {
        error: err instanceof Error ? err.message : "Something went wrong.",
      });
    } finally {
      updateAgentChat(agentId, { loading: false });
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
            {message.role === "assistant" ? <Markdown>{message.content}</Markdown> : message.content}
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
          onChange={(e) => updateAgentChat(agentId, { input: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          disabled={loading}
        />
        <button
          type="button"
          className="preview-chat-send"
          onClick={handleSend}
          disabled={loading || !input.trim()}
          aria-label="Send"
        >
          <ArrowUp size={16} />
        </button>
      </div>
    </div>
  );
}
