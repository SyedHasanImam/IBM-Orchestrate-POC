import { ArrowUp, Check, X } from "lucide-react";
import { api, type ChatResponse, type Decision } from "../api/client";
import {
  getAgentChat,
  updateAgentChat,
  useAgentChat,
  type AgentChatMessage,
} from "../state/agentChatHistory";
import { Button } from "./ui/Button";
import { Markdown } from "./ui/Markdown";
import "./AgentPreviewChat.css";

function messageFromResponse(data: ChatResponse): AgentChatMessage {
  if (data.pending_approval) {
    return {
      role: "approval",
      agentId: data.pending_approval.agent_id,
      report: data.pending_approval.report,
      approvalMessage: data.pending_approval.message,
      decision: null,
    };
  }
  return { role: "assistant", content: data.message, routedTo: data.routed_to };
}

export function AgentPreviewChat({ agentId }: { agentId: number }) {
  const { threadId, messages, input, loading, error, actor, comment, deciding } =
    useAgentChat(agentId);

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
        messages: [...getAgentChat(agentId).messages, messageFromResponse(data)],
      });
    } catch (err) {
      updateAgentChat(agentId, {
        error: err instanceof Error ? err.message : "Something went wrong.",
      });
    } finally {
      updateAgentChat(agentId, { loading: false });
    }
  }

  async function handleDecision(decision: Decision, messageIndex: number, reportAgentId: number) {
    const state = getAgentChat(agentId);
    if (!state.threadId) return;

    updateAgentChat(agentId, { deciding: true, error: null });
    try {
      const data = await api.submitAgentChatDecision(agentId, {
        thread_id: state.threadId,
        decision,
        actor: state.actor,
        comment: state.comment || null,
        // The report may belong to an Add Agent collaborator, not this
        // page's own agent — reportAgentId is whichever instance actually
        // generated it (see messageFromResponse).
        agent_id: reportAgentId,
      });
      const resolved = getAgentChat(agentId).messages.map((m, i) =>
        i === messageIndex && m.role === "approval" ? { ...m, decision } : m,
      );
      updateAgentChat(agentId, {
        threadId: data.thread_id,
        messages: [...resolved, messageFromResponse(data)],
      });
    } catch (err) {
      updateAgentChat(agentId, {
        error: err instanceof Error ? err.message : "Failed to submit decision.",
      });
    } finally {
      updateAgentChat(agentId, { deciding: false });
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
        {messages.map((message, index) => {
          if (message.role === "approval") {
            return (
              <div key={index} className="preview-chat-bubble preview-chat-bubble-approval">
                <p className="preview-chat-approval-message">{message.approvalMessage}</p>
                <div className="preview-chat-approval-report">
                  <Markdown>{message.report}</Markdown>
                </div>
                {message.decision ? (
                  <p className="preview-chat-approval-outcome">
                    {message.decision === "approved" ? "Approved." : "Rejected."}
                  </p>
                ) : (
                  <div className="preview-chat-approval-decision">
                    <label>
                      Your name
                      <input
                        type="text"
                        value={actor}
                        onChange={(e) => updateAgentChat(agentId, { actor: e.target.value })}
                      />
                    </label>
                    <label>
                      Comment (optional)
                      <input
                        type="text"
                        value={comment}
                        onChange={(e) => updateAgentChat(agentId, { comment: e.target.value })}
                      />
                    </label>
                    <div className="preview-chat-approval-buttons">
                      <Button
                        variant="primary"
                        size="sm"
                        disabled={!actor.trim() || deciding}
                        onClick={() => handleDecision("approved", index, message.agentId)}
                      >
                        <Check size={13} />
                        Approve
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={!actor.trim() || deciding}
                        onClick={() => handleDecision("rejected", index, message.agentId)}
                      >
                        <X size={13} />
                        Reject
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            );
          }
          return (
            <div
              key={index}
              className={`preview-chat-bubble preview-chat-bubble-${message.role}`}
            >
              {message.role === "assistant" ? <Markdown>{message.content}</Markdown> : message.content}
              {message.role === "assistant" && message.routedTo && (
                <div className="preview-chat-routed-to">Routed to: {message.routedTo}</div>
              )}
            </div>
          );
        })}
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
