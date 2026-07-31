import * as Tabs from "@radix-ui/react-tabs";
import { ArrowRight, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type TemplateDetail } from "../api/client";
import { AgentIcon } from "../components/ui/AgentIcon";
import { Button } from "../components/ui/Button";
import { formatSlug } from "../utils/format";
import "./TemplateDetailPage.css";

export function TemplateDetailPage() {
  const { name } = useParams();
  const navigate = useNavigate();
  const [template, setTemplate] = useState<TemplateDetail | null>(null);
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
        <Link to="/discover">Home</Link>
        <ChevronRight size={13} />
        <Link to="/discover">Agent Catalog</Link>
      </div>

      <div className="template-detail-header">
        <div className="template-detail-heading">
          <AgentIcon seed={template.name} size={48} />
          <div>
            <h1>{template.name}</h1>
            <p className="template-detail-tagline">{template.description}</p>
          </div>
        </div>
        <Button variant="primary" onClick={handleUseAsTemplate} disabled={creating}>
          {creating ? "Creating…" : "Use as template"}
          {!creating && <ArrowRight size={15} />}
        </Button>
      </div>

      {error && <p className="template-detail-error">{error}</p>}

      <Tabs.Root defaultValue="overview">
        <Tabs.List className="template-detail-tabs">
          <Tabs.Trigger value="overview" className="template-detail-tab">
            Overview
          </Tabs.Trigger>
          <Tabs.Trigger value="config" className="template-detail-tab">
            Configuration details
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="overview">
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
        </Tabs.Content>

        <Tabs.Content value="config">
          <div className="template-detail-body">
            <div className="template-detail-main">
              <h2>Tools</h2>
              <p className="template-detail-subtitle">Tools this template's stages use.</p>
              <div className="template-detail-nodes">
                {template.tools.map((toolName) => (
                  <div key={toolName} className="template-detail-node-card">
                    <span className="template-detail-node-name">{formatSlug(toolName)}</span>
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
                    <span className="template-detail-node-name">{formatSlug(node.name)}</span>
                    <span className="template-detail-node-type">{node.type}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
