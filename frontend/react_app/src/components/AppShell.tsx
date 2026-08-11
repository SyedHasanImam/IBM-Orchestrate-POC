import type { ReactNode } from "react";
import { useState } from "react";
import { PanelLeft, Sparkles } from "lucide-react";
import { AppSidebar } from "./AppSidebar";
import "./AppShell.css";

export function AppShell({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <button
          type="button"
          className="app-hamburger"
          aria-label="Toggle navigation"
          onClick={() => setSidebarOpen((open) => !open)}
        >
          <PanelLeft size={18} />
        </button>
        <div className="app-brand">
          <span className="app-brand-mark">
            <Sparkles size={15} />
          </span>
          <span className="app-topbar-title">oorchestrate poc</span>
        </div>
      </header>

      <div className="app-body">
        <AppSidebar collapsed={!sidebarOpen} />
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}
