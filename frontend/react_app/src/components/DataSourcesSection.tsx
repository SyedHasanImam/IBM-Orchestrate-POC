import { TriangleAlert, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type DataSourceStatus, type ReconciliationDocType } from "../api/client";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import "./DataSourcesSection.css";

export function DataSourcesSection({ agentId }: { agentId: number }) {
  const [sources, setSources] = useState<DataSourceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadingKey, setUploadingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  function load() {
    setLoading(true);
    api
      .getDataSources(agentId)
      .then(setSources)
      .catch(() => setSources([]))
      .finally(() => setLoading(false));
  }

  useEffect(load, [agentId]);

  async function handleFileSelected(
    source: DataSourceStatus,
    e: React.ChangeEvent<HTMLInputElement>,
  ) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setUploadingKey(source.key);
    setError(null);
    try {
      if (source.kind === "holdings") {
        await api.uploadHoldings(agentId, file);
      } else {
        await api.uploadReconciliationData(agentId, source.key as ReconciliationDocType, file);
      }
      toast.success(`${source.label} updated.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to upload ${source.label}.`);
    } finally {
      setUploadingKey(null);
    }
  }

  if (!loading && sources.length === 0) return null;

  return (
    <div className="data-sources-section">
      <h3>Upload documents</h3>
      <p className="data-sources-section-subtitle">
        The documents this agent's tools currently read from — whatever it needs out of
        the box, plus anything required by tools you've added in the Toolset tab. Each
        one is attached once and reused for every report until replaced.
      </p>

      {error && <p className="data-sources-section-error">{error}</p>}
      {loading && <p>Loading…</p>}

      {sources.map((source) => {
        const uploading = uploadingKey === source.key;
        return (
          <div key={source.key} className="data-sources-slot">
            <div className="data-sources-slot-header">
              <span className="data-sources-slot-label">{source.label}</span>
              {source.required && <Badge variant="warning">Required</Badge>}
            </div>
            <p className="data-sources-slot-description">{source.description}</p>

            {source.filename ? (
              <div className="data-sources-slot-status">
                <span className="data-sources-slot-filename">{source.filename}</span>
                <span className="data-sources-slot-meta">
                  {source.count} row{source.count === 1 ? "" : "s"}
                  {source.uploaded_at &&
                    ` · uploaded ${new Date(source.uploaded_at).toLocaleString()}`}
                </span>
              </div>
            ) : (
              <p className="data-sources-slot-empty">Not uploaded yet.</p>
            )}

            {source.warnings.length > 0 && (
              <div className="data-sources-slot-warnings">
                <p className="data-sources-slot-warnings-title">
                  <TriangleAlert size={13} />
                  These rows couldn't be read reliably and were left out:
                </p>
                <ul>
                  {source.warnings.map((w, i) => (
                    <li key={i}>
                      <strong>{w.row_reference}</strong> — {w.field}: {w.issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <input
              ref={(el) => {
                fileInputRefs.current[source.key] = el;
              }}
              type="file"
              accept={source.accept.join(",")}
              onChange={(e) => handleFileSelected(source, e)}
              style={{ display: "none" }}
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={() => fileInputRefs.current[source.key]?.click()}
              disabled={uploading}
            >
              <Upload size={13} />
              {uploading
                ? "Uploading…"
                : source.filename
                  ? `Replace ${source.label.toLowerCase()}`
                  : `Upload ${source.label.toLowerCase()} (${source.accept.join(", ")})`}
            </Button>
          </div>
        );
      })}
    </div>
  );
}
