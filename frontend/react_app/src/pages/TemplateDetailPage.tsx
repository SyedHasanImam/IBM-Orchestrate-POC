import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type TemplateDetail } from "../api/client";
import { formatSlug } from "../utils/format";
import "./TemplateDetailPage.css";

const TABS = ["Overview", "Configuration details"] as const;
type Tab = (typeof TABS)[number];

export function TemplateDetailPage() {
  const { name } = useParams();
  const navigate = useNavigate();
  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!name) return;
    api
      .getTemplate(name)
      .then(setTemplate)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load template."));
  }, [name]);

  async function handleUseAsTemplate() {
    if (!template) return;
    setCreating(true);
    setError(null);
    try {
      const instance = await api.createAgent(
        template.name,
        formatSlug(template.name),
        template.description,
      );
      navigate(`/agents/${instance.id}/edit`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create agent.");
      setCreating(false);
    }
  }

  if (error && !template) {
    return (
      <div className="template-detail-page">
        <p className="template-detail-error">{error}</p>
      </div>
    );
  }

  if (!template) {
    return <div className="template-detail-page">Loading…</div>;
  }

  return (
    <div className="template-detail-page">
      <div className="template-detail-breadcrumb">
        <Link to="/discover">Home</Link> / <Link to="/discover">Agent Catalog</Link>
      </div>

      <div className="template-detail-header">
        <h1>{template.name}</h1>
        <button
          type="button"
          className="template-detail-use"
          onClick={handleUseAsTemplate}
          disabled={creating}
        >
          {creating ? "Creating…" : "Use as template →"}
        </button>
      </div>

      {error && <p className="template-detail-error">{error}</p>}

      <nav className="template-detail-tabs">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            className={
              tab === activeTab
                ? "template-detail-tab template-detail-tab-active"
                : "template-detail-tab"
            }
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      {activeTab === "Overview" && (
        <div className="template-detail-body">
          <div className="template-detail-main">
            <h2>Description</h2>
            <p>{template.description}</p>
          </div>
          <div className="template-detail-sidebar">
            <div>
              <span className="template-detail-label">Version</span>
              <span>{template.version}</span>
            </div>
            <div>
              <span className="template-detail-label">Last updated</span>
              <span>{new Date(template.updated_at).toLocaleString()}</span>
            </div>
            <div>
              <span className="template-detail-label">Type</span>
              <span>Agent</span>
            </div>
          </div>
        </div>
      )}

      {activeTab === "Configuration details" && (
        <div className="template-detail-body">
          <div className="template-detail-main">
            <h2>Tools</h2>
            <p className="template-detail-subtitle">
              Tools this template's stages use.
            </p>
            <div className="template-detail-nodes">
              {template.tools.map((toolName) => (
                <div key={toolName} className="template-detail-node-card">
                  <span className="template-detail-node-name">
                    {formatSlug(toolName)}
                  </span>
                </div>
              ))}
            </div>

            <h2 className="template-detail-section-spaced">Agents</h2>
            <p className="template-detail-subtitle">
              The stages this template's pipeline runs, in fixed order.
            </p>
            <div className="template-detail-nodes">
              {template.nodes.map((node) => (
                <div key={node.name} className="template-detail-node-card">
                  <span className="template-detail-node-name">
                    {formatSlug(node.name)}
                  </span>
                  <span className="template-detail-node-type">{node.type}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
