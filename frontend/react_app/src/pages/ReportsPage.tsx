import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { api, type Decision, type DecisionResponse } from "../api/client";
import "./ReportsPage.css";

const WORKFLOW_NAME = "trustee_compliance_reporting";

export function ReportsPage() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [report, setReport] = useState<string | null>(null);
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
      const data = await api.runReport(WORKFLOW_NAME);
      setThreadId(data.thread_id);
      setReport(data.report);
      setFinalized(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run report.");
    } finally {
      setRunning(false);
    }
  }

  async function handleDecision(decision: Decision) {
    if (!threadId) return;
    setDeciding(true);
    setError(null);
    try {
      const data = await api.submitDecision(
        WORKFLOW_NAME,
        threadId,
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
    setThreadId(null);
    setReport(null);
    setFinalized(null);
    setActor("");
    setComment("");
    setError(null);
  }

  return (
    <div className="reports-page">
      <h1>Monthly Trustee Compliance Reporting</h1>

      <button type="button" onClick={handleRun} disabled={running || threadId !== null}>
        {running ? "Running the compliance pipeline…" : "Run Trustee Compliance Report"}
      </button>

      {error && <div className="reports-error">{error}</div>}

      {report && (
        <>
          <h2>Draft Report</h2>
          <div className="reports-draft">
            <ReactMarkdown>{report}</ReactMarkdown>
          </div>

          {!finalized && (
            <div className="reports-decision">
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
              <div className="reports-decision-buttons">
                <button
                  type="button"
                  className="reports-approve"
                  disabled={!actor.trim() || deciding}
                  onClick={() => handleDecision("approved")}
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="reports-reject"
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
                  ? "reports-finalized reports-finalized-approved"
                  : "reports-finalized reports-finalized-rejected"
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
