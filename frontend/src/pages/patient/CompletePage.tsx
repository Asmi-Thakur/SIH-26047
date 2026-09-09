/**
 * P10 — Completion (Phase 2c + Phase 4/2 polish).
 * Confirms the history reached the clinical team. For urgent cases the
 * deterministic red-flag wording is shown (spec §13.3 — no diagnosis).
 */
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { fetchCaseBySession } from "../../services/api";
import { t } from "../../utils/i18n";
import { useIntake } from "../../state/sessionStore";

export function CompletePage() {
  const { language, sessionId } = useIntake();

  const caseQuery = useQuery({
    queryKey: ["case", sessionId],
    queryFn: () => fetchCaseBySession(sessionId!),
    enabled: !!sessionId,
  });

  const urgent = caseQuery.data?.canonical?.triage?.priority === "urgent";

  return (
    <section className="mx-auto flex w-full max-w-xl flex-col items-center gap-6 px-4 py-16 text-center">
      <CheckCircle2 className="size-16 text-emerald-500" aria-hidden />
      <h1 className="text-3xl font-bold text-slate-900">
        {t(language, "nav.complete")}
      </h1>
      <p className="text-2xl font-medium text-slate-700">
        {t(language, "complete.sent")}
      </p>
      {urgent && (
        <p className="flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-lg font-semibold text-red-800">
          <ShieldAlert className="size-6 shrink-0" aria-hidden />
          {t(language, "complete.urgentNotice")}
        </p>
      )}
      <p className="text-lg text-slate-500">
        {t(language, "complete.thanks")}
      </p>
      <Link to="/patient/welcome" className="text-sm text-slate-400 underline">
        {t(language, "complete.newPatient")}
      </Link>
    </section>
  );
}
