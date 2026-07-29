import { useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  api,
  type Decision,
  type DecisionResponse,
  type RunReportResponse,
} from "../api/client";
import "./RunReportPanel.css";

export function RunReportPanel({ agentId }: { agentId: number }) {
  const [runResult, setRunResult] = useState<RunReportResponse | null>(null);
  const [finalized, setFinalized] = useState<DecisionResponse | null>(null);
  const [actor, setActor] = useState("");
  const [comment, setComment] = useState("");
  const [running, setRunning] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const data = await api.runAgentReport(agentId);
      setRunResult(data);
      setFinalized(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run report.");
    } finally {
      setRunning(false);
    }
  }

  async function handleDecision(decision: Decision) {
    if (!runResult) return;
    setDeciding(true);
    setError(null);
    try {
      const data = await api.submitDecision(
        runResult.workflow_name,
        runResult.thread_id,
        decision,
        actor,
        comment || null,
      );
      setFinalized(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit decision.");
    } finally {
      setDeciding(false);
    }
  }

  function handleReset() {
    setRunResult(null);
    setFinalized(null);
    setActor("");
    setComment("");
    setError(null);
  }

  return (
    <div className="run-report-panel">
      {!runResult && (
        <div className="run-report-setup">
          <p className="run-report-setup-subtitle">
            Runs against this agent's currently attached holdings and
            regulatory Knowledge — update either from the Edit configuration
            page first if they need to change.
          </p>
          <button type="button" onClick={handleRun} disabled={running}>
            {running ? "Running the compliance pipeline…" : "Run Report"}
          </button>
        </div>
      )}

      {error && <div className="run-report-error">{error}</div>}

      {runResult && (
        <>
          {runResult.extraction_warnings.length > 0 && (
            <div className="run-report-warnings">
              <h2>Extraction warnings</h2>
              <p className="run-report-warnings-subtitle">
                These rows from the uploaded document couldn't be read reliably,
                so they were left out of the report below rather than guessed —
                check the original document.
              </p>
              <ul>
                {runResult.extraction_warnings.map((w, i) => (
                  <li key={i}>
                    <strong>{w.row_reference}</strong> — {w.field}: {w.issue}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <h2>Draft Report</h2>
          <div className="run-report-draft">
            <ReactMarkdown>{runResult.report}</ReactMarkdown>
          </div>

          {!finalized && (
            <div className="run-report-decision">
              <h2>Reviewer Decision</h2>
              <label>
                Your name
                <input
                  type="text"
                  value={actor}
                  onChange={(e) => setActor(e.target.value)}
                />
              </label>
              <label>
                Comment (optional)
                <textarea value={comment} onChange={(e) => setComment(e.target.value)} />
              </label>
              <div className="run-report-decision-buttons">
                <button
                  type="button"
                  className="run-report-approve"
                  disabled={!actor.trim() || deciding}
                  onClick={() => handleDecision("approved")}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="run-report-reject"
                  disabled={!actor.trim() || deciding}
                  onClick={() => handleDecision("rejected")}
                >
                  Reject
                </button>
              </div>
            </div>
          )}

          {finalized && (
            <div
              className={
                finalized.event_type === "report_approved"
                  ? "run-report-finalized run-report-finalized-approved"
                  : "run-report-finalized run-report-finalized-rejected"
              }
            >
              {finalized.event_type === "report_approved"
                ? `Report approved and finalized. Audit log ID: ${finalized.audit_log_id}`
                : `Report rejected. Audit log ID: ${finalized.audit_log_id}`}
              <div>
                <button type="button" onClick={handleReset}>
                  Start a new report run
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
