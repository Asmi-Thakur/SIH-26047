/**
 * Triage console (Phase 3b).
 * Active deterministic red-flag alerts, refreshed every few seconds; staff
 * acknowledge them to clear the queue.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCheck, LoaderCircle } from "lucide-react";

import { acknowledgeAlert, fetchActiveAlerts } from "../../services/api";
import { t } from "../../utils/i18n";
import { useLanguage } from "../../state/sessionStore";

function timeLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function TriagePage() {
  const lang = useLanguage();
  const queryClient = useQueryClient();

  const alerts = useQuery({
    queryKey: ["triage"],
    queryFn: fetchActiveAlerts,
    refetchInterval: 5_000,
  });

  const acknowledge = useMutation({
    mutationFn: acknowledgeAlert,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["triage"] });
      void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  const items = alerts.data?.items ?? [];

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8">
      <h1 className="text-3xl font-bold text-slate-900">
        {t(lang, "nav.triage")}
      </h1>

      {alerts.isPending && (
        <div className="flex items-center gap-2 px-4 py-6 text-slate-500">
          <LoaderCircle className="size-5 animate-spin" aria-hidden />
          {t(lang, "triage.loading")}
        </div>
      )}
      {alerts.isError && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-red-700">
          {t(lang, "triage.error")}
        </p>
      )}

      {!alerts.isPending && !alerts.isError && items.length === 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white px-6 py-10 text-center text-slate-500">
          {t(lang, "triage.empty")}
        </div>
      )}

      <div className="flex flex-col gap-3">
        {items.map((alert) => (
          <div
            key={alert.alert_id}
            className="rounded-2xl border-2 border-red-200 bg-red-50 p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="flex items-center gap-2 font-bold text-red-700">
                <AlertTriangle className="size-5" aria-hidden />
                URGENT
              </span>
              <span className="text-sm text-red-500">
                {alert.token ?? "—"} · {timeLabel(alert.created_at)}
              </span>
            </div>
            <p className="mt-2 text-lg font-medium text-slate-900">
              {alert.message}
            </p>
            <p className="mt-1 text-sm text-slate-600">
              {alert.chief_complaint ?? "No chief complaint recorded yet"} ·{" "}
              {alert.rules_triggered.join(", ")}
            </p>
            <button
              type="button"
              disabled={acknowledge.isPending}
              onClick={() => acknowledge.mutate(alert.alert_id)}
              className="mt-3 inline-flex items-center gap-2 rounded-xl bg-red-600 px-5 py-2.5 font-semibold text-white disabled:opacity-40"
            >
              <CheckCheck className="size-4" aria-hidden />
              {t(lang, "triage.acknowledge")}
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
