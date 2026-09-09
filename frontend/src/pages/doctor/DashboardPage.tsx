/**
 * Doctor dashboard — live intake queue (Phase 3a).
 *
 * Reads real sessions from GET /api/sessions and refreshes every few
 * seconds, so a physician sees each patient's intake appear as it completes
 * on the kiosk. Triage urgency and document counts join in later phases.
 */
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  CheckCircle2,
  CircleSlash,
  Clock,
  Inbox,
  LoaderCircle,
} from "lucide-react";

import { cn } from "../../utils/cn";
import { Link } from "react-router-dom";

import { fetchActiveAlerts, listSessions } from "../../services/api";
import type { SessionListItem } from "../../types";
import { t } from "../../utils/i18n";
import { useLanguage } from "../../state/sessionStore";

function timeLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ConsentDot({ granted }: { granted: boolean | null | undefined }) {
  if (granted === true) {
    return <span className="size-2.5 rounded-full bg-emerald-500" title="Consent granted" />;
  }
  if (granted === false) {
    return <span className="size-2.5 rounded-full bg-red-400" title="Consent declined" />;
  }
  return <span className="size-2.5 rounded-full bg-amber-400" title="Consent pending" />;
}

function Row({ session }: { session: SessionListItem }) {
  const identity = session.token ?? session.patient_name ?? "—";
  return (
    <Link
      to={`/doctor/case/${session.session_id}`}
      className="grid grid-cols-[1.2fr_1fr_2fr_1.2fr_auto] items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left hover:border-indigo-300 hover:bg-indigo-50/40"
    >
      <span className="flex items-center gap-2 font-semibold text-slate-900">
        {identity}
        <ConsentDot granted={session.consent_granted} />
      </span>
      <span className="flex items-center gap-1.5 text-sm text-slate-500">
        <Clock className="size-4" aria-hidden />
        {timeLabel(session.started_at)}
      </span>
      <span className="truncate text-slate-700">
        {session.chief_complaint ?? "—"}
      </span>
      <span>
        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium capitalize text-slate-600">
          {session.state.replace(/_/g, " ")}
        </span>
      </span>
      {session.completed_at ? (
        <CheckCircle2 className="size-5 text-emerald-500" aria-hidden />
      ) : (
        <Activity className="size-5 text-indigo-400" aria-hidden />
      )}
    </Link>
  );
}

export function DashboardPage() {
  const lang = useLanguage();

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ["sessions"],
    queryFn: listSessions,
    refetchInterval: 10_000,
  });

  const triage = useQuery({
    queryKey: ["triage"],
    queryFn: fetchActiveAlerts,
    refetchInterval: 10_000,
  });

  const items = data?.items ?? [];
  const waiting = items.filter((s) => !s.completed_at);
  const completedCount = items.length - waiting.length;
  const consentedCount = items.filter((s) => s.consent_granted === true).length;
  const urgentCount = triage.data?.items.length ?? 0;

  const statClass =
    "flex flex-col gap-1 rounded-2xl border border-slate-200 bg-white p-5";
  const statValue = "text-3xl font-bold text-slate-900";
  const statLabel = "text-sm font-medium text-slate-500";

  return (
    <section className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-4 py-8">
      <h1 className="text-3xl font-bold text-slate-900">
        {t(lang, "nav.dashboard")}
      </h1>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className={statClass}>
          <span className={statValue}>{waiting.length}</span>
          <span className={statLabel}>{t(lang, "dashboard.waiting")}</span>
        </div>
        <div
          className={cn(
            statClass,
            urgentCount > 0 ? "border-red-300 bg-red-50" : undefined,
          )}
        >
          <span
            className={cn(
              statValue,
              urgentCount > 0 ? "text-red-700" : undefined,
            )}
          >
            {urgentCount}
          </span>
          <span className={statLabel}>{t(lang, "dashboard.urgent")}</span>
        </div>
        <div className={statClass}>
          <span className={statValue}>{completedCount}</span>
          <span className={statLabel}>{t(lang, "dashboard.completed")}</span>
        </div>
        <div className={statClass}>
          <span className={statValue}>{consentedCount}</span>
          <span className={statLabel}>{t(lang, "dashboard.consented")}</span>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <div className="grid grid-cols-[1.2fr_1fr_2fr_1.2fr_auto] items-center gap-3 px-4 text-xs font-semibold uppercase tracking-wide text-slate-400">
          <span>{t(lang, "dashboard.token")}</span>
          <span>{t(lang, "dashboard.time")}</span>
          <span>{t(lang, "dashboard.complaint")}</span>
          <span>{t(lang, "dashboard.state")}</span>
          <span />
        </div>

        {isPending && (
          <div className="flex items-center gap-2 px-4 py-6 text-slate-500">
            <LoaderCircle className="size-5 animate-spin" aria-hidden />
            {t(lang, "dashboard.loading")}
          </div>
        )}
        {isError && (
          <button
            type="button"
            onClick={() => void refetch()}
            className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-left text-red-700"
          >
            <CircleSlash className="size-5 shrink-0" aria-hidden />
            {t(lang, "dashboard.retry")}
          </button>
        )}
        {!isPending && !isError && waiting.length === 0 && (
          <div className="flex items-center gap-2 px-4 py-6 text-slate-500">
            <Inbox className="size-5 shrink-0" aria-hidden />
            {t(lang, "dashboard.empty")}
          </div>
        )}

        {waiting.map((session) => (
          <Row key={session.session_id} session={session} />
        ))}
      </div>
    </section>
  );
}
