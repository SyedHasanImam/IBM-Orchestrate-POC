import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type AgentInstance } from "../api/client";
import { AgentPreviewChat } from "../components/AgentPreviewChat";
import { KnowledgeTab } from "../components/KnowledgeTab";
import { ToolsetTab } from "../components/ToolsetTab";
import { notifyAgentsChanged } from "../state/agentEvents";
import "./AgentEditorPage.css";

const TABS = ["Profile", "Knowledge", "Toolset", "Behavior", "Channels"] as const;
type Tab = (typeof TABS)[number];

export function AgentEditorPage() {
  const { agentId } = useParams();
  const navigate = useNavigate();

  const [agent, setAgent] = useState<AgentInstance | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("Profile");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!agentId) return;
    api.getAgent(Number(agentId)).then((data) => {
      setAgent(data);
      setDisplayName(data.display_name);
      setDescription(data.description);
    });
  }, [agentId]);

  async function handleSave() {
    if (!agent) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateAgent(agent.id, {
        display_name: displayName,
        description,
      });
      setAgent(updated);
      if (updated.status === "deployed") notifyAgentsChanged();
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
      const updated = await api.updateAgent(agent.id, { display_name: displayName, description });
      await api.deployAgent(updated.id);
      notifyAgentsChanged();
      navigate(`/agents/${updated.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deploy.");
      setDeploying(false);
    }
  }

  async function handleDelete() {
    if (!agent) return;
    if (!window.confirm(`Delete "${agent.display_name}"? This can't be undone.`)) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deleteAgent(agent.id);
      notifyAgentsChanged();
      navigate("/discover");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete.");
      setDeleting(false);
    }
  }

  if (!agent) {
    return <div className="agent-editor-page">Loading…</div>;
  }

  return (
    <div className="agent-editor-page">
      <div className="agent-editor-header">
        <div>
          <h1>{agent.display_name}</h1>
          <p className="agent-editor-subtitle">
            From template: {agent.template_name} ·{" "}
            <span className={`agent-editor-status agent-editor-status-${agent.status}`}>
              {agent.status}
            </span>
          </p>
        </div>
        <div className="agent-editor-header-actions">
          <button type="button" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            className="agent-editor-deploy"
            onClick={handleDeploy}
            disabled={deploying}
          >
            {deploying ? "Deploying…" : "Deploy"}
          </button>
          <button
            type="button"
            className="agent-editor-delete"
            onClick={handleDelete}
            disabled={deleting}
          >
            {deleting ? "Deleting…" : "Delete"}
          </button>
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
                <label>
                  Description
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </label>
              </div>
            )}

            {activeTab === "Knowledge" && <KnowledgeTab agentId={agent.id} />}

            {activeTab === "Toolset" && <ToolsetTab templateName={agent.template_name} />}

            {activeTab !== "Profile" &&
              activeTab !== "Knowledge" &&
              activeTab !== "Toolset" && (
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
    </div>
  );
}
