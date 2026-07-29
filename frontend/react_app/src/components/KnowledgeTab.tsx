import { useEffect, useRef, useState } from "react";
import { api, type AgentDocument } from "../api/client";
import { HoldingsSection } from "./HoldingsSection";
import "./KnowledgeTab.css";

export function KnowledgeTab({ agentId }: { agentId: number }) {
  const [documents, setDocuments] = useState<AgentDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload document.");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(documentId: number) {
    setDeletingId(documentId);
    setError(null);
    try {
      await api.deleteDocument(agentId, documentId);
      setDocuments((prev) => prev.filter((d) => d.id !== documentId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete document.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="knowledge-tab">
      <HoldingsSection agentId={agentId} />

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
              <div>
                <span className="knowledge-tab-filename">{doc.filename}</span>
                <span className="knowledge-tab-meta">
                  {doc.chunk_count} chunk{doc.chunk_count === 1 ? "" : "s"} · added{" "}
                  {new Date(doc.created_at).toLocaleString()}
                </span>
              </div>
              <button
                type="button"
                className="knowledge-tab-delete"
                onClick={() => handleDelete(doc.id)}
                disabled={deletingId === doc.id}
              >
                {deletingId === doc.id ? "Removing…" : "Remove"}
              </button>
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
      <button
        type="button"
        className="knowledge-tab-upload"
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
      >
        {uploading ? "Uploading…" : "Upload document (.md, .txt)"}
      </button>
    </div>
  );
}
