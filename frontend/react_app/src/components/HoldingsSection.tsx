import { TriangleAlert, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type HoldingsSnapshot } from "../api/client";
import { Button } from "./ui/Button";
import "./HoldingsSection.css";

export function HoldingsSection({ agentId }: { agentId: number }) {
  const [snapshot, setSnapshot] = useState<HoldingsSnapshot | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.getHoldings(agentId).then(setSnapshot);
  }, [agentId]);

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      const data = await api.uploadHoldings(agentId, file);
      setSnapshot(data);
      toast.success(`Holdings updated — ${data.holdings_count} positions.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload holdings.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="holdings-section">
      <h3>Holdings</h3>
      <p className="holdings-section-subtitle">
        This period's holdings snapshot — used every time you Run Report on
        this agent. Replace it whenever the numbers change.
      </p>

      {error && <p className="holdings-section-error">{error}</p>}

      {snapshot && snapshot.filename ? (
        <div className="holdings-section-status">
          <span className="holdings-section-filename">{snapshot.filename}</span>
          <span className="holdings-section-meta">
            {snapshot.holdings_count} position{snapshot.holdings_count === 1 ? "" : "s"}
            {snapshot.uploaded_at &&
              ` · uploaded ${new Date(snapshot.uploaded_at).toLocaleString()}`}
          </span>
        </div>
      ) : (
        <p className="holdings-section-empty">No holdings uploaded yet.</p>
      )}

      {snapshot && snapshot.warnings.length > 0 && (
        <div className="holdings-section-warnings">
          <p className="holdings-section-warnings-title">
            <TriangleAlert size={14} />
            These rows couldn't be read reliably and were left out:
          </p>
          <ul>
            {snapshot.warnings.map((w, i) => (
              <li key={i}>
                <strong>{w.row_reference}</strong> — {w.field}: {w.issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx,.pdf"
        onChange={handleFileSelected}
        style={{ display: "none" }}
      />
      <Button variant="secondary" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
        <Upload size={15} />
        {uploading
          ? "Uploading…"
          : snapshot?.filename
            ? "Replace holdings file"
            : "Upload holdings file (.xlsx, .pdf)"}
      </Button>
    </div>
  );
}
