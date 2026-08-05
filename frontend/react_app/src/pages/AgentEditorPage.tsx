import { Rocket, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { api, type AgentInstance } from "../api/client";
import { AgentPreviewChat } from "../components/AgentPreviewChat";
import { KnowledgeTab } from "../components/KnowledgeTab";
import { ToolsetTab } from "../components/ToolsetTab";
import { AgentIcon } from "../components/ui/AgentIcon";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { notifyAgentsChanged } from "../state/agentEvents";
import "./AgentEditorPage.css";

const TABS = ["Profile", "Knowledge", "Toolset", "Behavior", "Channels"] as const;
type Tab = (typeof TABS)[number];

const INSTRUCTIONS_PLACEHOLDER = `**Tool Usage Guidelines**
1. Before calling a tool, make sure you have everything you need — ask the user for any required parameter you don't already have rather than assuming a value.
2. Don't call the same tool again with the same parameters if you already have that result.
3. If a question is unrelated to this agent's job, say so honestly instead of guessing.
4. If a tool returns more than one data point, show the results as a table.`;

export function AgentEditorPage() {
  const { agentId } = useParams();
  const navigate = useNavigate();

  const [agent, setAgent] = useState<AgentInstance | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("Profile");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [temperature, setTemperature] = useState("");
  const [maxTokens, setMaxTokens] = useState("");
  const [saving, setSaving] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!agentId) return;
    api.getAgent(Number(agentId)).then((data) => {
      setAgent(data);
      setDisplayName(data.display_name);
      setDescription(data.description);
      setInstructions(data.instructions ?? "");
      setTemperature(data.llm_config.temperature?.toString() ?? "");
      setMaxTokens(data.llm_config.max_tokens?.toString() ?? "");
    });
  }, [agentId]);

  function currentLlmConfig() {
    return {
      temperature: temperature.trim() === "" ? null : Number(temperature),
      max_tokens: maxTokens.trim() === "" ? null : Number(maxTokens),
    };
  }

  async function handleSave() {
    if (!agent) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateAgent(agent.id, {
        display_name: displayName,
        description,
        instructions,
        llm_config: currentLlmConfig(),
      });
      setAgent(updated);
      if (updated.status === "deployed") notifyAgentsChanged();
      toast.success("Changes saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeploy() {
    if (!agent) return;
    setDeploying(true);
    setError(null);
    try {
      const updated = await api.updateAgent(agent.id, {
        display_name: displayName,
        description,
        instructions,
        llm_config: currentLlmConfig(),
      });
      await api.deployAgent(updated.id);
      notifyAgentsChanged();
      toast.success(`"${displayName}" deployed.`);
      navigate(`/agents/${updated.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deploy.");
      setDeploying(false);
    }
  }

  async function handleDelete() {
    if (!agent) return;
    await api.deleteAgent(agent.id);
    notifyAgentsChanged();
    toast.success(`"${agent.display_name}" deleted.`);
    navigate("/discover");
  }

  if (!agent) {
    return <div className="agent-editor-page">Loading…</div>;
  }

  return (
    <div className="agent-editor-page">
      <div className="agent-editor-header">
        <div className="agent-editor-heading">
          <AgentIcon seed={agent.template_name + agent.id} size={40} />
          <div>
            <h1>{agent.display_name}</h1>
            <p className="agent-editor-subtitle">
              From template: {agent.template_name} ·{" "}
              <Badge variant={agent.status === "deployed" ? "success" : "neutral"}>
                {agent.status}
              </Badge>
            </p>
          </div>
        </div>
        <div className="agent-editor-header-actions">
          <Button variant="secondary" onClick={handleSave} disabled={saving}>
            <Save size={15} />
            {saving ? "Saving…" : "Save"}
          </Button>
          <Button variant="primary" onClick={handleDeploy} disabled={deploying}>
            <Rocket size={15} />
            {deploying ? "Deploying…" : "Deploy"}
          </Button>
          <Button variant="danger" onClick={() => setConfirmingDelete(true)}>
            <Trash2 size={15} />
            Delete
          </Button>
        </div>
      </div>

      {error && <p className="agent-editor-error">{error}</p>}

      <div className="agent-editor-body">
        <div className="agent-editor-left">
          <nav className="agent-editor-tabs">
            {TABS.map((tab) => (
              <button
                key={tab}
                type="button"
                className={
                  tab === activeTab
                    ? "agent-editor-tab agent-editor-tab-active"
                    : "agent-editor-tab"
                }
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            ))}
          </nav>

          <div className="agent-editor-panel">
            {activeTab === "Profile" && (
              <div>
                <label>
                  Agent name
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                  />
                </label>
                <p className="agent-editor-hint">
                  This is what the homepage chat's routing reads to decide whether a
                  question goes to this agent — mention its specific tools and data (e.g.
                  "checks single-issuer and sector exposure limits using the fund's
                  holdings"), not just its general domain, so routing and search can match
                  on more than a vague topic label.
                </p>
                <label>
                  Description
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </label>
              </div>
            )}

            {activeTab === "Knowledge" && (
              <KnowledgeTab agentId={agent.id} />
            )}

            {activeTab === "Toolset" && (
              <ToolsetTab agent={agent} onAgentUpdated={setAgent} />
            )}

            {activeTab === "Behavior" && (
              <div>
                <p className="agent-editor-hint">
                  Instructions shape how {agent.display_name} behaves and uses its tools —
                  layered on top of its Description above, never replacing it. Leave this
                  blank to use sensible defaults.
                </p>
                <label>
                  Instructions
                  <textarea
                    className="agent-editor-behavior-textarea"
                    value={instructions}
                    onChange={(e) => setInstructions(e.target.value)}
                    placeholder={INSTRUCTIONS_PLACEHOLDER}
                  />
                </label>

                <p className="agent-editor-hint agent-editor-model-settings-hint">
                  Model settings — optional overrides for this agent's answers. Leave
                  blank to use the template's plain model with no override.
                </p>
                <div className="agent-editor-model-settings-row">
                  <label>
                    Temperature (0–2)
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="2"
                      value={temperature}
                      onChange={(e) => setTemperature(e.target.value)}
                      placeholder="default"
                    />
                  </label>
                  <label>
                    Max tokens
                    <input
                      type="number"
                      min="1"
                      value={maxTokens}
                      onChange={(e) => setMaxTokens(e.target.value)}
                      placeholder="default"
                    />
                  </label>
                </div>
              </div>
            )}

            {activeTab === "Channels" && (
              <p className="agent-editor-placeholder">
                {activeTab} configuration is coming in a later stage.
              </p>
            )}
          </div>
        </div>

        <div className="agent-editor-preview">
          <div className="agent-editor-preview-header">Preview</div>
          <AgentPreviewChat key={agent.id} agentId={agent.id} />
        </div>
      </div>

      <ConfirmDialog
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
        title={`Delete "${agent.display_name}"?`}
        description="This can't be undone. The agent, its Knowledge, and its attached data will be permanently removed."
        confirmLabel="Delete"
        danger
        onConfirm={handleDelete}
      />
    </div>
  );
}
