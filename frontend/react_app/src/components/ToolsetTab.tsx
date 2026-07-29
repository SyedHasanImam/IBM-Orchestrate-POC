import { useEffect, useState } from "react";
import { api, type TemplateDetail } from "../api/client";
import { formatSlug } from "../utils/format";
import "./ToolsetTab.css";

export function ToolsetTab({ templateName }: { templateName: string }) {
  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getTemplate(templateName)
      .then(setTemplate)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load."))
      .finally(() => setLoading(false));
  }, [templateName]);

  return (
    <div className="toolset-tab">
      {loading && <p>Loading…</p>}
      {error && <p className="toolset-tab-error">{error}</p>}

      {!loading && !error && template && (
        <>
          <div className="toolset-tab-section-header">
            <div>
              <h2>Tools</h2>
              <p className="toolset-tab-subtitle">Tools this agent's stages use.</p>
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
              <h2>Agents</h2>
              <p className="toolset-tab-subtitle">
                Agents this one can delegate tasks to.
              </p>
            </div>
            <button type="button" className="toolset-tab-add" disabled>
              Add agent +
            </button>
          </div>
          <div className="toolset-tab-cards">
            {template.nodes.map((node) => (
              <div key={node.name} className="toolset-tab-card">
                <span className="toolset-tab-card-name">{formatSlug(node.name)}</span>
                <span className="toolset-tab-card-type">{node.type}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
