import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import "./AppShell.css";

const NAV_ITEMS = [
  { to: "/chat", label: "Chat" },
  { to: "/discover", label: "Discover" },
  { to: "/reports", label: "Reports" },
];

const DISABLED_NAV_ITEMS = [
  { label: "Build", hint: "Coming in a later stage" },
  { label: "Manage", hint: "Coming in a later stage" },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="app-topbar">
        <span className="app-topbar-title">Fund Management Agent Platform</span>
      </header>
      <div className="app-body">
        <nav className="app-sidebar">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                isActive ? "app-nav-item app-nav-item-active" : "app-nav-item"
              }
            >
              {item.label}
            </NavLink>
          ))}
          <div className="app-sidebar-divider" />
          {DISABLED_NAV_ITEMS.map((item) => (
            <span
              key={item.label}
              className="app-nav-item app-nav-item-disabled"
              title={item.hint}
            >
              {item.label}
            </span>
          ))}
        </nav>
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}
