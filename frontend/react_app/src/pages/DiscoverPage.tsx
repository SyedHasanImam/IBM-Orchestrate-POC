import { useEffect, useState } from "react";
import { api, type CatalogEntry } from "../api/client";
import "./DiscoverPage.css";

export function DiscoverPage() {
  const [entries, setEntries] = useState<CatalogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getCatalog()
      .then(setEntries)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load catalog."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="discover-page">
      <h1>Agent Catalog</h1>
      <p className="discover-subtitle">
        Pulled live from the agent registry — new workflows appear here once
        their config is loaded, with no frontend code changes.
      </p>

      {loading && <p>Loading…</p>}
      {error && <p className="discover-error">{error}</p>}

      {!loading && !error && entries.length === 0 && <p>No agents registered yet.</p>}

      <div className="discover-grid">
        {entries.map((entry) => (
          <div key={entry.name} className="discover-card">
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
    </div>
  );
}
