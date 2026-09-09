/**
 * Application shell: header with navigation, backend health badge, and the
 * routed page below.
 *
 * Phase 1 shows the full navigation skeleton so the patient flow and the
 * doctor console are reachable from day one. Kiosk styling (large touch
 * targets, audio controls) arrives with the real screens in Phase 2.
 */
import { HeartPulse } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { cn } from "../../utils/cn";
import { t } from "../../utils/i18n";
import { useLanguage } from "../../state/sessionStore";
import { HealthBadge } from "../ui/HealthBadge";

const patientNav = [
  { to: "/patient/welcome", key: "nav.welcome" as const },
  { to: "/patient/identity", key: "nav.identity" as const },
  { to: "/patient/consent", key: "nav.consent" as const },
  { to: "/patient/interview", key: "nav.interview" as const },
  { to: "/patient/documents", key: "nav.documents" as const },
  { to: "/patient/review", key: "nav.review" as const },
  { to: "/patient/complete", key: "nav.complete" as const },
];

const doctorNav = [
  { to: "/doctor/dashboard", key: "nav.dashboard" as const },
  { to: "/doctor/triage", key: "nav.triage" as const },
];

function linkClass({ isActive }: { isActive: boolean }): string {
  return cn(
    "rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors",
    isActive
      ? "bg-indigo-100 text-indigo-800"
      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
  );
}

export function AppShell() {
  const lang = useLanguage();

  return (
    <div className="flex min-h-screen flex-col bg-white text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <NavLink to="/patient/welcome" className="flex items-center gap-2">
            <HeartPulse className="size-6 text-indigo-600" aria-hidden />
            <span className="text-lg font-semibold">{t(lang, "appName")}</span>
          </NavLink>
          <HealthBadge />
        </div>

        <nav className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-1 border-t border-slate-100 px-4 py-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {t(lang, "nav.patientFlow")}
          </span>
          {patientNav.map((item) => (
            <NavLink key={item.to} to={item.to} className={linkClass}>
              {t(lang, item.key)}
            </NavLink>
          ))}

          <span className="ml-4 text-xs font-semibold uppercase tracking-wide text-slate-400">
            {t(lang, "nav.doctorConsole")}
          </span>
          {doctorNav.map((item) => (
            <NavLink key={item.to} to={item.to} className={linkClass}>
              {t(lang, item.key)}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 py-3 text-center text-xs text-slate-400">
        MediKiosk · SIH 2026 · PS 26047 — prototype, not a medical device
      </footer>
    </div>
  );
}