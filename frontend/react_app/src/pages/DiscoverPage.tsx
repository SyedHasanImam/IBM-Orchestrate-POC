import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type AgentInstance, type CatalogEntry } from "../api/client";
import { notifyAgentsChanged } from "../state/agentEvents";
import "./DiscoverPage.css";

type Tab = "catalog" | "mine";

function matchesSearch(search: string, ...fields: string[]): boolean {
  if (!search.trim()) return true;
  const needle = search.trim().toLowerCase();
  return fields.some((field) => field.toLowerCase().includes(needle));
}

export function DiscoverPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<Tab>("catalog");
  const [search, setSearch] = useState("");
  const [templates, setTemplates] = useState<CatalogEntry[]>([]);
  const [agents, setAgents] = useState<AgentInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([api.getCatalog(), api.listAgents()])
      .then(([catalogEntries, agentInstances]) => {
        setTemplates(catalogEntries);
        setAgents(agentInstances.filter((a) => a.status === "deployed"));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load catalog."))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(agent: AgentInstance, e: React.MouseEvent) {
    e.stopPropagation();
    if (!window.confirm(`Delete "${agent.display_name}"? This can't be undone.`)) return;
    setDeletingId(agent.id);
    setError(null);
    try {
      await api.deleteAgent(agent.id);
      setAgents((prev) => prev.filter((a) => a.id !== agent.id));
      notifyAgentsChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete agent.");
    } finally {
      setDeletingId(null);
    }
  }

  const filteredTemplates = useMemo(
    () => templates.filter((t) => matchesSearch(search, t.name, t.description)),
    [templates, search],
  );
  const filteredAgents = useMemo(
    () => agents.filter((a) => matchesSearch(search, a.display_name, a.description)),
    [agents, search],
  );

  return (
    <div className="discover-page">
      <h1>Discover agents and tools</h1>
      <p className="discover-subtitle">
        Explore pre-built agents and customize your own from them.
      </p>

      <input
        type="text"
        className="discover-search"
        placeholder="Search the catalog"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <div className="discover-tabs">
        <button
          type="button"
          className={activeTab === "catalog" ? "discover-tab discover-tab-active" : "discover-tab"}
          onClick={() => setActiveTab("catalog")}
        >
          Complete catalog
        </button>
        <button
          type="button"
          className={activeTab === "mine" ? "discover-tab discover-tab-active" : "discover-tab"}
          onClick={() => setActiveTab("mine")}
        >
          My agents and tools
        </button>
      </div>

      {loading && <p>Loading…</p>}
      {error && <p className="discover-error">{error}</p>}

      {!loading && !error && activeTab === "catalog" && (
        <div className="discover-grid">
          {filteredTemplates.length === 0 && <p>No templates match your search.</p>}
          {filteredTemplates.map((entry) => (
            <div
              key={entry.name}
              className="discover-card discover-card-clickable"
              onClick={() => navigate(`/templates/${entry.name}`)}
            >
              <div className="discover-card-header">
                <span className="discover-card-name">{entry.name}</span>
                <span className="discover-card-version">v{entry.version}</span>
              </div>
              <p className="discover-card-description">{entry.description}</p>
              <p className="discover-card-updated">
                Updated {new Date(entry.updated_at).toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      )}

      {!loading && !error && activeTab === "mine" && (
        <div className="discover-grid">
          {filteredAgents.length === 0 && <p>No agents match your search.</p>}
          {filteredAgents.map((agent) => (
            <div key={agent.id} className="discover-card">
              <div className="discover-card-header">
                <span className="discover-card-name">{agent.display_name}</span>
                <span className="discover-card-version">from {agent.template_name}</span>
              </div>
              <p className="discover-card-description">{agent.description}</p>
              <p className="discover-card-updated">
                Updated {new Date(agent.updated_at).toLocaleString()}
              </p>
              <div className="discover-card-actions">
                <button
                  type="button"
                  className="discover-card-action"
                  onClick={() => navigate(`/agents/${agent.id}/edit`)}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="discover-card-action discover-card-action-delete"
                  onClick={(e) => handleDelete(agent, e)}
                  disabled={deletingId === agent.id}
                >
                  {deletingId === agent.id ? "Deleting…" : "Delete"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
