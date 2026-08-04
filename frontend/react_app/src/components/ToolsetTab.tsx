import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type AgentInstance, type TemplateDetail } from "../api/client";
import { AddToolDialog } from "./AddToolDialog";
import { Button } from "./ui/Button";
import { formatSlug } from "../utils/format";
import "./ToolsetTab.css";

export function ToolsetTab({
  agent,
  onAgentUpdated,
}: {
  agent: AgentInstance;
  onAgentUpdated: (agent: AgentInstance) => void;
}) {
  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addToolOpen, setAddToolOpen] = useState(false);
  const [removingName, setRemovingName] = useState<string | null>(null);

  useEffect(() => {
    api
      .getTemplate(agent.template_name)
      .then(setTemplate)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load."))
      .finally(() => setLoading(false));
  }, [agent.template_name]);

  async function handleAddTool(toolName: string) {
    const updated = await api.updateAgent(agent.id, {
      extra_tools: [...agent.extra_tools, toolName],
    });
    onAgentUpdated(updated);
    toast.success(`${formatSlug(toolName)} added.`);
  }

  async function handleRemoveTool(toolName: string) {
    setRemovingName(toolName);
    try {
      const updated = await api.updateAgent(agent.id, {
        extra_tools: agent.extra_tools.filter((t) => t !== toolName),
      });
      onAgentUpdated(updated);
      toast.success(`${formatSlug(toolName)} removed.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove tool.");
    } finally {
      setRemovingName(null);
    }
  }

  return (
    <div className="toolset-tab">
      {loading && <p>Loading…</p>}
      {error && <p className="toolset-tab-error">{error}</p>}

      {!loading && !error && template && (
        <>
          <div className="toolset-tab-section-header">
            <div>
              <h2>Tools</h2>
              <p className="toolset-tab-subtitle">
                Built into this agent's template — always available.
              </p>
            </div>
          </div>
          <div className="toolset-tab-cards">
            {template.tools.map((toolName) => (
              <div key={toolName} className="toolset-tab-card">
                <span className="toolset-tab-card-name">{formatSlug(toolName)}</span>
              </div>
            ))}
          </div>

          <div className="toolset-tab-section-header toolset-tab-section-header-spaced">
            <div>
              <h2>Added tools</h2>
              <p className="toolset-tab-subtitle">
                Extra tools you've given this specific agent, beyond its template.
              </p>
            </div>
            <Button variant="secondary" size="sm" onClick={() => setAddToolOpen(true)}>
              <Plus size={14} />
              Add tool
            </Button>
          </div>
          <div className="toolset-tab-cards">
            {agent.extra_tools.length === 0 && (
              <p className="toolset-tab-empty">No extra tools added yet.</p>
            )}
            {agent.extra_tools.map((toolName) => (
              <div key={toolName} className="toolset-tab-card">
                <span className="toolset-tab-card-name">{formatSlug(toolName)}</span>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => handleRemoveTool(toolName)}
                  disabled={removingName === toolName}
                >
                  <Trash2 size={13} />
                  {removingName === toolName ? "Removing…" : "Remove"}
                </Button>
              </div>
            ))}
          </div>

          <div className="toolset-tab-section-header toolset-tab-section-header-spaced">
            <div>
              <h2>Agents</h2>
              <p className="toolset-tab-subtitle">
                Agents this one can delegate tasks to.
              </p>
            </div>
            <Button variant="secondary" size="sm" disabled title="Coming in a later stage">
              <Plus size={14} />
              Add agent
            </Button>
          </div>
          <div className="toolset-tab-cards">
            {template.nodes.map((node) => (
              <div key={node.name} className="toolset-tab-card">
                <span className="toolset-tab-card-name">{formatSlug(node.name)}</span>
                <span className="toolset-tab-card-type">{node.type}</span>
              </div>
            ))}
          </div>

          <AddToolDialog
            open={addToolOpen}
            onOpenChange={setAddToolOpen}
            excludeToolNames={[...template.tools, ...agent.extra_tools]}
            onAdd={handleAddTool}
          />
        </>
      )}
    </div>
  );
}
