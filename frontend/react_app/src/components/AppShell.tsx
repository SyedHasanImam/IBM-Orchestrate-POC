import type { ReactNode } from "react";
import { useState } from "react";
import { NavLink } from "react-router-dom";
import { AppSidebar } from "./AppSidebar";
import "./AppShell.css";

const DISABLED_OVERLAY_ITEMS = [
  { label: "Build", hint: "Coming in a later stage" },
  { label: "Manage", hint: "Coming in a later stage" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <button
          type="button"
          className="app-hamburger"
          aria-label="Toggle navigation"
          onClick={() => setNavOpen((open) => !open)}
        >
          <span />
          <span />
          <span />
        </button>
        <span className="app-topbar-title">Fund Management Agent Platform</span>
      </header>

      <div className="app-body">
        <AppSidebar />
        <main className="app-content">{children}</main>
      </div>

      {navOpen && (
        <div className="app-nav-overlay" onClick={() => setNavOpen(false)}>
          <nav className="app-nav-overlay-panel" onClick={(e) => e.stopPropagation()}>
            <NavLink
              to="/discover"
              className={({ isActive }) =>
                isActive ? "app-overlay-item app-overlay-item-active" : "app-overlay-item"
              }
              onClick={() => setNavOpen(false)}
            >
              Discover
            </NavLink>
            {DISABLED_OVERLAY_ITEMS.map((item) => (
              <span
                key={item.label}
                className="app-overlay-item app-overlay-item-disabled"
                title={item.hint}
              >
                {item.label}
              </span>
            ))}
          </nav>
        </div>
      )}
    </div>
  );
}
