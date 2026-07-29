import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { api, type AgentInstance } from "../api/client";
import { onAgentsChanged } from "../state/agentEvents";
import "./AppSidebar.css";

export function AppSidebar() {
  const [agents, setAgents] = useState<AgentInstance[]>([]);

  function loadAgents() {
    api.listAgents().then((all) => setAgents(all.filter((a) => a.status === "deployed")));
  }

  useEffect(() => {
    loadAgents();
    return onAgentsChanged(loadAgents);
  }, []);

  return (
    <nav className="app-sidebar">
      <NavLink
        to="/chat"
        end
        className={({ isActive }) =>
          isActive ? "app-sidebar-item app-sidebar-item-active" : "app-sidebar-item"
        }
      >
        Chat
      </NavLink>

      <button type="button" className="app-sidebar-new-chat">
        + New chat
      </button>

      <div className="app-sidebar-divider" />
      <div className="app-sidebar-title">Your Agents</div>

      {agents.length === 0 && (
        <p className="app-sidebar-empty">No deployed agents yet.</p>
      )}

      {agents.map((agent) => (
        <NavLink
          key={agent.id}
          to={`/agents/${agent.id}`}
          end
          className={({ isActive }) =>
            isActive ? "app-sidebar-item app-sidebar-item-active" : "app-sidebar-item"
          }
        >
          {agent.display_name}
        </NavLink>
      ))}
    </nav>
  );
}
