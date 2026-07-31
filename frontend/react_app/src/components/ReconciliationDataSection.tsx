import { TriangleAlert, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type ReconciliationDataOut, type ReconciliationDocType } from "../api/client";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import "./ReconciliationDataSection.css";

const SLOTS: { docType: ReconciliationDocType; label: string; required: boolean }[] = [
  { docType: "ledger", label: "Fund Ledger", required: true },
  { docType: "custodian_statement", label: "Custodian Statement", required: true },
  { docType: "trade_blotter", label: "Trade Blotter", required: false },
  { docType: "corporate_actions", label: "Corporate Actions Calendar", required: false },
];

export function ReconciliationDataSection({ agentId }: { agentId: number }) {
  const [data, setData] = useState<Partial<Record<ReconciliationDocType, ReconciliationDataOut>>>(
    {},
  );
  const [uploadingType, setUploadingType] = useState<ReconciliationDocType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRefs = useRef<Partial<Record<ReconciliationDocType, HTMLInputElement | null>>>(
    {},
  );

  function load() {
    api.getReconciliationData(agentId).then((rows) => {
      const map: Partial<Record<ReconciliationDocType, ReconciliationDataOut>> = {};
      rows.forEach((row) => (map[row.doc_type] = row));
      setData(map);
    });
  }

  useEffect(load, [agentId]);

  async function handleFileSelected(
    docType: ReconciliationDocType,
    label: string,
    e: React.ChangeEvent<HTMLInputElement>,
  ) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    setUploadingType(docType);
    setError(null);
    try {
      const result = await api.uploadReconciliationData(agentId, docType, file);
      setData((prev) => ({ ...prev, [docType]: result }));
      toast.success(`${label} updated — ${result.row_count} rows.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to upload ${docType}.`);
    } finally {
      setUploadingType(null);
    }
  }

  return (
    <div className="reconciliation-data-section">
      <h3>Reconciliation data</h3>
      <p className="reconciliation-data-section-subtitle">
        The ledger and custodian statement are compared every time you Run Report. Trade
        blotter and corporate actions are optional — attaching them lets more breaks get
        automatically explained instead of flagged as unexplained.
      </p>

      {error && <p className="reconciliation-data-section-error">{error}</p>}

      {SLOTS.map(({ docType, label, required }) => {
        const slot = data[docType];
        const uploading = uploadingType === docType;
        return (
          <div key={docType} className="reconciliation-data-slot">
            <div className="reconciliation-data-slot-header">
              <span className="reconciliation-data-slot-label">{label}</span>
              {required && <Badge variant="warning">Required</Badge>}
            </div>

            {slot?.filename ? (
              <div className="reconciliation-data-slot-status">
                <span className="reconciliation-data-slot-filename">{slot.filename}</span>
                <span className="reconciliation-data-slot-meta">
                  {slot.row_count} row{slot.row_count === 1 ? "" : "s"}
                  {slot.uploaded_at &&
                    ` · uploaded ${new Date(slot.uploaded_at).toLocaleString()}`}
                </span>
              </div>
            ) : (
              <p className="reconciliation-data-slot-empty">Not uploaded yet.</p>
            )}

            {slot && slot.warnings.length > 0 && (
              <div className="reconciliation-data-slot-warnings">
                <p className="reconciliation-data-slot-warnings-title">
                  <TriangleAlert size={13} />
                  These rows couldn't be read reliably and were left out:
                </p>
                <ul>
                  {slot.warnings.map((w, i) => (
                    <li key={i}>
                      <strong>{w.row_reference}</strong> — {w.field}: {w.issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <input
              ref={(el) => {
                fileInputRefs.current[docType] = el;
              }}
              type="file"
              accept=".xlsx"
              onChange={(e) => handleFileSelected(docType, label, e)}
              style={{ display: "none" }}
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={() => fileInputRefs.current[docType]?.click()}
              disabled={uploading}
            >
              <Upload size={13} />
              {uploading
                ? "Uploading…"
                : slot?.filename
                  ? `Replace ${label.toLowerCase()}`
                  : `Upload ${label.toLowerCase()} (.xlsx)`}
            </Button>
          </div>
        );
      })}
    </div>
  );
}
