import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type AgentInstance } from "../api/client";
import { notifyAgentsChanged } from "../state/agentEvents";
import { AgentIcon } from "./ui/AgentIcon";
import { Switch } from "./ui/Switch";
import "./ChatAgentPicker.css";

export function ChatAgentPicker({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [agents, setAgents] = useState<AgentInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    api
      .listAgents()
      .then((all) => setAgents(all.filter((a) => a.status === "deployed")))
      .finally(() => setLoading(false));
  }, [open]);

  async function handleToggle(agent: AgentInstance, checked: boolean) {
    setTogglingId(agent.id);
    setAgents((prev) =>
      prev.map((a) => (a.id === agent.id ? { ...a, included_in_chat: checked } : a)),
    );
    try {
      await api.updateAgent(agent.id, { included_in_chat: checked });
      notifyAgentsChanged();
    } catch (err) {
      setAgents((prev) =>
        prev.map((a) => (a.id === agent.id ? { ...a, included_in_chat: !checked } : a)),
      );
      toast.error(err instanceof Error ? err.message : "Failed to update.");
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="chat-agent-picker-overlay" />
        <Dialog.Content className="chat-agent-picker-content">
          <div className="chat-agent-picker-header">
            <Dialog.Title className="chat-agent-picker-title">Manage agents</Dialog.Title>
            <Dialog.Close asChild>
              <button type="button" className="chat-agent-picker-close" aria-label="Close">
                <X size={16} />
              </button>
            </Dialog.Close>
          </div>
          <Dialog.Description className="chat-agent-picker-description">
            Choose which deployed agents this chat can route questions to. With none
            selected, it's just a general assistant with no access to your fund data.
          </Dialog.Description>

          {loading && <p className="chat-agent-picker-empty">Loading…</p>}
          {!loading && agents.length === 0 && (
            <p className="chat-agent-picker-empty">
              No deployed agents yet — deploy one from Discover first.
            </p>
          )}

          <div className="chat-agent-picker-list">
            {agents.map((agent) => (
              <div key={agent.id} className="chat-agent-picker-row">
                <AgentIcon seed={agent.template_name + agent.id} size={32} />
                <div className="chat-agent-picker-row-info">
                  <span className="chat-agent-picker-row-name">{agent.display_name}</span>
                  <span className="chat-agent-picker-row-desc">{agent.description}</span>
                </div>
                <Switch
                  checked={agent.included_in_chat}
                  onCheckedChange={(checked) => handleToggle(agent, checked)}
                  disabled={togglingId === agent.id}
                  aria-label={`Include ${agent.display_name} in chat`}
                />
              </div>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
