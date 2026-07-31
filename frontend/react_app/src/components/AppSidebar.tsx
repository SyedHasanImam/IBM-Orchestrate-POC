import clsx from "clsx";
import { Compass, Inbox, MessageCircle, SquarePen } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { api, type AgentInstance } from "../api/client";
import { onAgentsChanged } from "../state/agentEvents";
import { AgentIcon } from "./ui/AgentIcon";
import "./AppSidebar.css";

export function AppSidebar({ collapsed }: { collapsed: boolean }) {
  const [agents, setAgents] = useState<AgentInstance[]>([]);
  const navigate = useNavigate();

  function loadAgents() {
    api.listAgents().then((all) => setAgents(all.filter((a) => a.status === "deployed")));
  }

  useEffect(() => {
    loadAgents();
    return onAgentsChanged(loadAgents);
  }, []);

  return (
    <nav className={clsx("app-sidebar", collapsed && "app-sidebar-collapsed")}>
      <div className="app-sidebar-inner">
        <div className="app-sidebar-primary">
          <NavLink
            to="/chat"
            end
            className={({ isActive }) =>
              clsx("app-sidebar-item", isActive && "app-sidebar-item-active")
            }
          >
            <MessageCircle size={17} />
            <span>Chat</span>
          </NavLink>
          <NavLink
            to="/discover"
            className={({ isActive }) =>
              clsx("app-sidebar-item", isActive && "app-sidebar-item-active")
            }
          >
            <Compass size={17} />
            <span>Discover</span>
          </NavLink>
        </div>

        <button
          type="button"
          className="app-sidebar-new-chat"
          onClick={() => navigate("/chat")}
        >
          <SquarePen size={15} />
          <span>New chat</span>
        </button>

        <div className="app-sidebar-divider" />
        <div className="app-sidebar-title">Your Agents</div>

        {agents.length === 0 && (
          <div className="app-sidebar-empty">
            <Inbox size={16} />
            <span>No deployed agents yet.</span>
          </div>
        )}

        <div className="app-sidebar-agents">
          {agents.map((agent) => (
            <NavLink
              key={agent.id}
              to={`/agents/${agent.id}`}
              end
              className={({ isActive }) =>
                clsx("app-sidebar-item", "app-sidebar-agent", isActive && "app-sidebar-item-active")
              }
            >
              <AgentIcon seed={agent.template_name + agent.id} size={22} />
              <span className="app-sidebar-agent-name">{agent.display_name}</span>
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
}
