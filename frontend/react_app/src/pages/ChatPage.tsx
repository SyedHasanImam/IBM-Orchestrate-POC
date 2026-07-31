import { ArrowUp, Sparkles, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, type AgentInstance } from "../api/client";
import { ChatAgentPicker } from "../components/ChatAgentPicker";
import { AgentIcon } from "../components/ui/AgentIcon";
import { Markdown } from "../components/ui/Markdown";
import { onAgentsChanged } from "../state/agentEvents";
import {
  getChatHistory,
  resetChatHistory,
  updateChatHistory,
  useChatHistory,
} from "../state/chatHistory";
import "./ChatPage.css";

// Known templates get curated, realistic questions; anything else (a future
// third agent type) still gets a reasonable generic suggestion rather than
// nothing at all.
const TEMPLATE_SUGGESTIONS: Record<string, string[]> = {
  trustee_compliance_reporting: [
    "What holdings does the fund currently have?",
    "What's our current exposure to a single issuer?",
    "Summarize the fund's compliance status this month.",
  ],
  stock_reconciliation: [
    "Are there any unexplained reconciliation breaks right now?",
    "Why is the OGDC position unexplained?",
    "What explains the difference in the Cherat Cement position?",
  ],
};

const NO_AGENT_SUGGESTIONS = [
  "What can you help me with?",
  "How do I add an agent to this chat?",
];

const MAX_SUGGESTIONS = 4;

function suggestionsFor(agents: AgentInstance[]): string[] {
  if (agents.length === 0) return NO_AGENT_SUGGESTIONS;

  const perAgent = agents.length === 1 ? 3 : 2;
  const picked: string[] = [];
  for (const agent of agents) {
    const options = TEMPLATE_SUGGESTIONS[agent.template_name] ?? [
      `Ask ${agent.display_name} what it can help with.`,
    ];
    picked.push(...options.slice(0, perAgent));
  }
  return picked.slice(0, MAX_SUGGESTIONS);
}

export function ChatPage() {
  const { threadId, messages, input, loading, error } = useChatHistory();
  const [includedAgents, setIncludedAgents] = useState<AgentInstance[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);

  function loadIncludedAgents() {
    api
      .listAgents()
      .then((all) =>
        setIncludedAgents(all.filter((a) => a.status === "deployed" && a.included_in_chat)),
      );
  }

  useEffect(() => {
    loadIncludedAgents();
    return onAgentsChanged(loadIncludedAgents);
  }, []);

  const suggestions = useMemo(() => suggestionsFor(includedAgents), [includedAgents]);

  async function sendMessage(question: string) {
    if (!question.trim()) return;

    updateChatHistory({
      messages: [...getChatHistory().messages, { role: "user", content: question }],
      input: "",
      loading: true,
      error: null,
    });

    try {
      const data = await api.chat(question, threadId);
      updateChatHistory({
        threadId: data.thread_id,
        messages: [
          ...getChatHistory().messages,
          { role: "assistant", content: data.message, routedTo: data.routed_to },
        ],
      });
    } catch (err) {
      updateChatHistory({
        error: err instanceof Error ? err.message : "Something went wrong.",
      });
    } finally {
      updateChatHistory({ loading: false });
    }
  }

  function handleNewConversation() {
    resetChatHistory();
  }

  const started = messages.length > 0;

  return (
    <div className="chat-page">
      <div className="chat-agents-bar">
        {includedAgents.length === 0 ? (
          <span className="chat-agents-bar-empty">General chat — no agents added yet</span>
        ) : (
          <div className="chat-agents-bar-list">
            {includedAgents.map((agent) => (
              <span key={agent.id} className="chat-agents-bar-chip">
                <AgentIcon seed={agent.template_name + agent.id} size={18} />
                {agent.display_name}
              </span>
            ))}
          </div>
        )}
        <button
          type="button"
          className="chat-agents-bar-manage"
          onClick={() => setPickerOpen(true)}
        >
          <Users size={14} />
          Manage agents
        </button>
      </div>

      {!started ? (
        <div className="chat-welcome">
          <span className="chat-welcome-mark">
            <Sparkles size={22} />
          </span>
          <h1 className="chat-welcome-title">What can I help you with?</h1>
          <p className="chat-welcome-subtitle">
            {includedAgents.length > 0
              ? "Ask a question and it's routed to the specialist agent best suited to answer it — no need to run a full report for a quick question."
              : "This is a general chat for now — add an agent above to get grounded answers about your fund's actual data."}
          </p>

          <div className="chat-input-row chat-input-row-hero">
            <input
              type="text"
              value={input}
              placeholder="Ask about holdings, compliance, or reconciliation…"
              onChange={(e) => updateChatHistory({ input: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === "Enter") sendMessage(input);
              }}
              disabled={loading}
              autoFocus
            />
            <button
              type="button"
              className="chat-send"
              onClick={() => sendMessage(input)}
              disabled={loading || !input.trim()}
              aria-label="Send"
            >
              <ArrowUp size={18} />
            </button>
          </div>

          <div className="chat-suggestions">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="chat-suggestion-chip"
                onClick={() => sendMessage(suggestion)}
                disabled={loading}
              >
                {suggestion}
              </button>
            ))}
          </div>

          {error && <div className="chat-error">{error}</div>}
        </div>
      ) : (
        <>
          <div className="chat-window">
            {messages.map((message, index) => (
              <div key={index} className={`chat-bubble chat-bubble-${message.role}`}>
                {message.role === "assistant" ? (
                  <Markdown>{message.content}</Markdown>
                ) : (
                  <div className="chat-bubble-content">{message.content}</div>
                )}
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
              placeholder="Ask a follow-up…"
              onChange={(e) => updateChatHistory({ input: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === "Enter") sendMessage(input);
              }}
              disabled={loading}
            />
            <button
              type="button"
              className="chat-send"
              onClick={() => sendMessage(input)}
              disabled={loading || !input.trim()}
              aria-label="Send"
            >
              <ArrowUp size={18} />
            </button>
          </div>

          <button type="button" className="chat-reset" onClick={handleNewConversation}>
            Start a new conversation
          </button>
        </>
      )}

      <ChatAgentPicker open={pickerOpen} onOpenChange={setPickerOpen} />
    </div>
  );
}
