import type { ReactNode } from "react";
import { getBoot } from "../api/client";
import { ICONS } from "./icons";
import { PatientPicker } from "./PatientPicker";
import { useRoutes } from "./RoutesContext";
import { hrefFor, ROUTES, useRoute } from "./router";

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";
}

export function Shell({ children }: { children: ReactNode }) {
  const route = useRoute();
  const { user } = getBoot();
  const { can_approve } = useRoutes();
  return (
    <div className="shell">
      <nav className="nav" aria-label="ABHA tasks">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">H</span>
          <div>
            <div className="brand-name">Health Central</div>
            <div className="brand-sub">ABHA desk</div>
          </div>
        </div>
        <div className="nav-label">Tasks</div>
        <ul className="nav-list">
          {ROUTES.filter((r) => r.id !== "approvals" || can_approve || r.id === route.id).map((r) => {
            const Icon = ICONS[r.id];
            return (
              <li key={r.id}>
                <a className="nav-link" href={hrefFor(r.id)} aria-current={r.id === route.id ? "page" : undefined}>
                  <Icon />
                  <span>{r.label}</span>
                </a>
              </li>
            );
          })}
        </ul>
        <div className="nav-foot">
          <a className="nav-link" href="/app/patient">Back to desk</a>
        </div>
      </nav>
      <div className="workspace">
        <header className="topbar">
          <nav aria-label="Breadcrumb" className="crumbs">
            <span>Healthcare</span><span className="crumb-sep" aria-hidden="true">/</span>
            <span>Patient registration</span><span className="crumb-sep" aria-hidden="true">/</span>
            <span aria-current="page">{route.label}</span>
          </nav>
          <div className="topbar-right">
            <PatientPicker />
            <span className="avatar" title={user.full_name} aria-label={`Signed in as ${user.full_name}`}>{initials(user.full_name)}</span>
          </div>
        </header>
        <main className="main" id="main">
          <h1 className="page-title">{route.label}</h1>
          <p className="page-sub">{route.hint}</p>
          {children}
        </main>
      </div>
    </div>
  );
}
