import * as Dialog from "@radix-ui/react-dialog";
import { Plus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type AgentInstance } from "../api/client";
import "./AddAgentDialog.css";

export function AddAgentDialog({
  open,
  onOpenChange,
  currentAgentId,
  excludeAgentIds,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentAgentId: number;
  excludeAgentIds: number[];
  onAdd: (agentId: number) => Promise<void>;
}) {
  const [agents, setAgents] = useState<AgentInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [addingId, setAddingId] = useState<number | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    api
      .listAgents()
      .then(setAgents)
      .finally(() => setLoading(false));
  }, [open]);

  // Only deployed agents can actually answer at chat time — an undeployed
  // one would just silently drop out of the roster, so it's excluded here
  // too rather than offering something that wouldn't really work yet.
  const available = agents.filter(
    (agent) =>
      agent.status === "deployed" &&
      agent.id !== currentAgentId &&
      !excludeAgentIds.includes(agent.id),
  );

  async function handleAdd(agentId: number) {
    setAddingId(agentId);
    try {
      await onAdd(agentId);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add agent.");
    } finally {
      setAddingId(null);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="add-agent-dialog-overlay" />
        <Dialog.Content className="add-agent-dialog-content">
          <div className="add-agent-dialog-header">
            <Dialog.Title className="add-agent-dialog-title">Add an agent</Dialog.Title>
            <Dialog.Close asChild>
              <button type="button" className="add-agent-dialog-close" aria-label="Close">
                <X size={16} />
              </button>
            </Dialog.Close>
          </div>
          <Dialog.Description className="add-agent-dialog-description">
            Choose a deployed agent for this one to delegate to — a fixed part of this
            agent's own roster, not a runtime choice. Useful for consolidating several
            narrower agents behind one description, so the homepage chat has one lean
            agent to route to instead of many overlapping ones.
          </Dialog.Description>

          {loading && <p className="add-agent-dialog-empty">Loading…</p>}
          {!loading && available.length === 0 && (
            <p className="add-agent-dialog-empty">
              No other deployed agents are available to add.
            </p>
          )}

          <div className="add-agent-dialog-list">
            {available.map((agent) => (
              <button
                key={agent.id}
                type="button"
                className="add-agent-dialog-row"
                onClick={() => handleAdd(agent.id)}
                disabled={addingId !== null}
              >
                <div className="add-agent-dialog-row-info">
                  <span className="add-agent-dialog-row-name">{agent.display_name}</span>
                  <span className="add-agent-dialog-row-desc">{agent.description}</span>
                </div>
                {addingId === agent.id ? (
                  <span className="add-agent-dialog-row-adding">Adding…</span>
                ) : (
                  <Plus size={15} />
                )}
              </button>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
