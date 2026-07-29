import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type AgentInstance } from "../api/client";
import { AgentPreviewChat } from "../components/AgentPreviewChat";
import { RunReportPanel } from "../components/RunReportPanel";
import "./AgentPage.css";

export function AgentPage() {
  const { agentId } = useParams();
  const [agent, setAgent] = useState<AgentInstance | null>(null);

  useEffect(() => {
    if (!agentId) return;
    api.getAgent(Number(agentId)).then(setAgent);
  }, [agentId]);

  if (!agent) {
    return <div className="agent-page">Loading…</div>;
  }

  if (agent.status !== "deployed") {
    return (
      <div className="agent-page">
        <p>
          <strong>{agent.display_name}</strong> hasn't been deployed yet.{" "}
          <Link to={`/agents/${agent.id}/edit`}>Finish configuring it</Link> first.
        </p>
      </div>
    );
  }

  return (
    <div className="agent-page">
      <div className="agent-page-header">
        <div>
          <h1>{agent.display_name}</h1>
          <p className="agent-page-subtitle">{agent.description}</p>
        </div>
        <Link to={`/agents/${agent.id}/edit`} className="agent-page-edit-link">
          Edit configuration
        </Link>
      </div>

      <div className="agent-page-body">
        <div className="agent-page-left">
          <RunReportPanel key={agent.id} agentId={agent.id} />
        </div>

        <div className="agent-page-preview">
          <div className="agent-page-preview-header">Chat</div>
          <AgentPreviewChat key={agent.id} agentId={agent.id} />
        </div>
      </div>
    </div>
  );
}
