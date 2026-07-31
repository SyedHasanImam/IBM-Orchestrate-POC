import { FileText, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type AgentDocument } from "../api/client";
import { HoldingsSection } from "./HoldingsSection";
import { ReconciliationDataSection } from "./ReconciliationDataSection";
import { Button } from "./ui/Button";
import "./KnowledgeTab.css";

const HOLDINGS_DEPENDENT_TOOLS = ["get_fund_holdings", "get_portfolio_exposure_summary"];
const RECONCILIATION_DEPENDENT_TOOLS = [
  "get_fund_ledger",
  "get_custodian_statement",
  "get_trade_blotter",
  "get_corporate_actions",
  "match_positions",
];

export function KnowledgeTab({
  agentId,
  templateName,
}: {
  agentId: number;
  templateName: string;
}) {
  const [documents, setDocuments] = useState<AgentDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showHoldings, setShowHoldings] = useState(false);
  const [showReconciliationData, setShowReconciliationData] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .getTemplate(templateName)
      .then((template) => {
        setShowHoldings(template.tools.some((t) => HOLDINGS_DEPENDENT_TOOLS.includes(t)));
        setShowReconciliationData(
          template.tools.some((t) => RECONCILIATION_DEPENDENT_TOOLS.includes(t)),
        );
      })
      .catch(() => {
        setShowHoldings(false);
        setShowReconciliationData(false);
      });
  }, [templateName]);

  function loadDocuments() {
    setLoading(true);
    api
      .listDocuments(agentId)
      .then(setDocuments)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load documents."))
      .finally(() => setLoading(false));
  }

  useEffect(loadDocuments, [agentId]);

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      const document = await api.uploadDocument(agentId, file);
      setDocuments((prev) => [...prev, document]);
      toast.success(`"${document.filename}" attached.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload document.");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(documentId: number, filename: string) {
    setDeletingId(documentId);
    setError(null);
    try {
      await api.deleteDocument(agentId, documentId);
      setDocuments((prev) => prev.filter((d) => d.id !== documentId));
      toast.success(`"${filename}" removed.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete document.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="knowledge-tab">
      {showHoldings && <HoldingsSection agentId={agentId} />}
      {showReconciliationData && <ReconciliationDataSection agentId={agentId} />}

      <h3>Regulatory documents</h3>
      <p className="knowledge-tab-subtitle">
        Regulatory documents this agent checks holdings against — the investment
        mandate, SECP excerpts, or any fund's rules. Attached here once, reused
        across every report this agent generates.
      </p>

      {error && <p className="knowledge-tab-error">{error}</p>}
      {loading && <p>Loading…</p>}

      {!loading && documents.length === 0 && (
        <p className="knowledge-tab-empty">No documents attached yet.</p>
      )}

      {!loading && documents.length > 0 && (
        <ul className="knowledge-tab-list">
          {documents.map((doc) => (
            <li key={doc.id} className="knowledge-tab-item">
              <div className="knowledge-tab-item-info">
                <FileText size={16} className="knowledge-tab-item-icon" />
                <div>
                  <span className="knowledge-tab-filename">{doc.filename}</span>
                  <span className="knowledge-tab-meta">
                    {doc.chunk_count} chunk{doc.chunk_count === 1 ? "" : "s"} · added{" "}
                    {new Date(doc.created_at).toLocaleString()}
                  </span>
                </div>
              </div>
              <Button
                variant="danger"
                size="sm"
                onClick={() => handleDelete(doc.id, doc.filename)}
                disabled={deletingId === doc.id}
              >
                <Trash2 size={13} />
                {deletingId === doc.id ? "Removing…" : "Remove"}
              </Button>
            </li>
          ))}
        </ul>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".md,.txt"
        onChange={handleFileSelected}
        style={{ display: "none" }}
      />
      <Button variant="secondary" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
        <Upload size={15} />
        {uploading ? "Uploading…" : "Upload document (.md, .txt)"}
      </Button>
    </div>
  );
}
