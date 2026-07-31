import * as Tabs from "@radix-ui/react-tabs";
import { Search, SquarePen, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, type AgentInstance, type CatalogEntry } from "../api/client";
import { notifyAgentsChanged } from "../state/agentEvents";
import { AgentIcon } from "../components/ui/AgentIcon";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import "./DiscoverPage.css";

function matchesSearch(search: string, ...fields: string[]): boolean {
  if (!search.trim()) return true;
  const needle = search.trim().toLowerCase();
  return fields.some((field) => field.toLowerCase().includes(needle));
}

export function DiscoverPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"catalog" | "mine">("catalog");
  const [search, setSearch] = useState("");
  const [templates, setTemplates] = useState<CatalogEntry[]>([]);
  const [agents, setAgents] = useState<AgentInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<AgentInstance | null>(null);

  useEffect(() => {
    Promise.all([api.getCatalog(), api.listAgents()])
      .then(([catalogEntries, agentInstances]) => {
        setTemplates(catalogEntries);
        setAgents(agentInstances.filter((a) => a.status === "deployed"));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load catalog."))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete() {
    if (!pendingDelete) return;
    await api.deleteAgent(pendingDelete.id);
    setAgents((prev) => prev.filter((a) => a.id !== pendingDelete.id));
    notifyAgentsChanged();
    toast.success(`"${pendingDelete.display_name}" deleted.`);
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

      <div className="discover-search-row">
        <Search size={16} className="discover-search-icon" />
        <input
          type="text"
          className="discover-search"
          placeholder="Search the catalog"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <Tabs.Root
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as "catalog" | "mine")}
        className="discover-tabs-root"
      >
        <Tabs.List className="discover-tabs">
          <Tabs.Trigger value="catalog" className="discover-tab">
            Complete catalog
          </Tabs.Trigger>
          <Tabs.Trigger value="mine" className="discover-tab">
            My agents and tools
          </Tabs.Trigger>
        </Tabs.List>

        {loading && <p className="discover-loading">Loading…</p>}
        {error && <p className="discover-error">{error}</p>}

        <Tabs.Content value="catalog">
          {!loading && !error && (
            <div className="discover-grid">
              {filteredTemplates.length === 0 && (
                <p className="discover-empty">No templates match your search.</p>
              )}
              {filteredTemplates.map((entry) => (
                <div
                  key={entry.name}
                  className="discover-card discover-card-clickable"
                  onClick={() => navigate(`/templates/${entry.name}`)}
                >
                  <div className="discover-card-header">
                    <AgentIcon seed={entry.name} />
                    <div className="discover-card-heading">
                      <span className="discover-card-name">{entry.name}</span>
                      <Badge variant="neutral">v{entry.version}</Badge>
                    </div>
                  </div>
                  <p className="discover-card-description">{entry.description}</p>
                  <p className="discover-card-updated">
                    Updated {new Date(entry.updated_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Tabs.Content>

        <Tabs.Content value="mine">
          {!loading && !error && (
            <div className="discover-grid">
              {filteredAgents.length === 0 && (
                <p className="discover-empty">No agents match your search.</p>
              )}
              {filteredAgents.map((agent) => (
                <div key={agent.id} className="discover-card">
                  <div className="discover-card-header">
                    <AgentIcon seed={agent.template_name + agent.id} />
                    <div className="discover-card-heading">
                      <span className="discover-card-name">{agent.display_name}</span>
                      <Badge variant="primary">from {agent.template_name}</Badge>
                    </div>
                  </div>
                  <p className="discover-card-description">{agent.description}</p>
                  <p className="discover-card-updated">
                    Updated {new Date(agent.updated_at).toLocaleString()}
                  </p>
                  <div className="discover-card-actions">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => navigate(`/agents/${agent.id}/edit`)}
                    >
                      <SquarePen size={14} />
                      Edit
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => setPendingDelete(agent)}
                    >
                      <Trash2 size={14} />
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Tabs.Content>
      </Tabs.Root>

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
        title={`Delete "${pendingDelete?.display_name}"?`}
        description="This can't be undone. The agent, its Knowledge, and its attached data will be permanently removed."
        confirmLabel="Delete"
        danger
        onConfirm={handleDelete}
      />
    </div>
  );
}
