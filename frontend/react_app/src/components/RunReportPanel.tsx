import { Check, TriangleAlert, X } from "lucide-react";
import { toast } from "sonner";
import { api, type Decision } from "../api/client";
import { resetReportRun, updateReportRun, useReportRun } from "../state/reportRuns";
import { Button } from "./ui/Button";
import { Markdown } from "./ui/Markdown";
import "./RunReportPanel.css";

export function RunReportPanel({ agentId }: { agentId: number }) {
  const { runResult, finalized, actor, comment, running, deciding, error } =
    useReportRun(agentId);

  async function handleRun() {
    updateReportRun(agentId, { running: true, error: null });
    try {
      const data = await api.runAgentReport(agentId);
      updateReportRun(agentId, { runResult: data, finalized: null });
    } catch (err) {
      updateReportRun(agentId, {
        error: err instanceof Error ? err.message : "Failed to run report.",
      });
    } finally {
      updateReportRun(agentId, { running: false });
    }
  }

  async function handleDecision(decision: Decision) {
    if (!runResult) return;
    updateReportRun(agentId, { deciding: true, error: null });
    try {
      const data = await api.submitDecision(
        runResult.workflow_name,
        runResult.thread_id,
        decision,
        actor,
        comment || null,
      );
      updateReportRun(agentId, { finalized: data });
      toast.success(decision === "approved" ? "Report approved." : "Report rejected.");
    } catch (err) {
      updateReportRun(agentId, {
        error: err instanceof Error ? err.message : "Failed to submit decision.",
      });
    } finally {
      updateReportRun(agentId, { deciding: false });
    }
  }

  function handleReset() {
    resetReportRun(agentId);
  }

  return (
    <div className="run-report-panel">
      {!runResult && (
        <div className="run-report-setup">
          <p className="run-report-setup-subtitle">
            Runs this agent's report pipeline against its configured data
            sources and Knowledge — update either from the Edit
            configuration page first if they need to change.
          </p>
          <Button variant="primary" onClick={handleRun} disabled={running}>
            {running ? "Running the pipeline…" : "Run Report"}
          </Button>
        </div>
      )}

      {error && <div className="run-report-error">{error}</div>}

      {runResult && (
        <>
          {runResult.extraction_warnings.length > 0 && (
            <div className="run-report-warnings">
              <h2>
                <TriangleAlert size={16} />
                Extraction warnings
              </h2>
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

          <h2 className="run-report-draft-heading">Draft Report</h2>
          <div className="run-report-draft">
            <Markdown>{runResult.report}</Markdown>
          </div>

          {!finalized && (
            <div className="run-report-decision">
              <h2>Reviewer Decision</h2>
              <label>
                Your name
                <input
                  type="text"
                  value={actor}
                  onChange={(e) => updateReportRun(agentId, { actor: e.target.value })}
                />
              </label>
              <label>
                Comment (optional)
                <textarea
                  value={comment}
                  onChange={(e) => updateReportRun(agentId, { comment: e.target.value })}
                />
              </label>
              <div className="run-report-decision-buttons">
                <Button
                  variant="primary"
                  disabled={!actor.trim() || deciding}
                  onClick={() => handleDecision("approved")}
                >
                  <Check size={15} />
                  Approve
                </Button>
                <Button
                  variant="danger"
                  disabled={!actor.trim() || deciding}
                  onClick={() => handleDecision("rejected")}
                >
                  <X size={15} />
                  Reject
                </Button>
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
                <Button variant="secondary" size="sm" onClick={handleReset}>
                  Start a new report run
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
