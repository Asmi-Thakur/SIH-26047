/**
 * P03 — Consent (Phase 2c).
 * Plain-language explanation + explicit grant or decline. Declining still
 * allows the interview but blocks document processing/export downstream
 * (enforced by later modules per the spec).
 */
import { useMutation } from "@tanstack/react-query";
import { CircleAlert, Volume2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { recordConsent } from "../../services/api";
import { ApiError } from "../../services/api";
import { t } from "../../utils/i18n";
import { useIntake } from "../../state/sessionStore";

const purposes = ["clinical_intake", "document_processing"];

export function ConsentPage() {
  const navigate = useNavigate();
  const { language, sessionId } = useIntake();

  const consent = useMutation({
    mutationFn: (granted: boolean) =>
      recordConsent(sessionId!, {
        granted,
        purposes: granted ? purposes : [],
        consent_text_version: "v1",
      }),
    onSuccess: () => navigate("/patient/interview"),
  });

  if (!sessionId) {
    return (
      <section className="mx-auto max-w-xl px-4 py-10">
        <p className="text-lg text-slate-600">
          Please start from the Welcome screen first.
        </p>
        <a href="/patient/welcome" className="mt-4 inline-block text-indigo-600">
          {t(language, "welcome.start")}
        </a>
      </section>
    );
  }

  const errorMessage =
    consent.isError && consent.error instanceof ApiError
      ? consent.error.detail?.message ?? consent.error.message
      : consent.isError
        ? "Could not save your choice."
        : null;

  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-6 px-4 py-10">
      <h1 className="text-3xl font-bold text-slate-900">
        {t(language, "nav.consent")}
      </h1>

      <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-6">
        <p className="text-xl font-semibold text-slate-900">
          {t(language, "consent.what")}
        </p>
        <ul className="flex flex-col gap-3 text-lg text-slate-700">
          <li>• {t(language, "consent.item1")}</li>
          <li>• {t(language, "consent.item2")}</li>
          <li>• {t(language, "consent.item3")}</li>
          <li>• {t(language, "consent.item4")}</li>
        </ul>
        <button
          type="button"
          className="inline-flex items-center gap-2 self-start rounded-xl border border-slate-300 px-4 py-2 font-medium text-slate-600"
          title="Audio explanation arrives with the voice milestone"
        >
          <Volume2 className="size-4" aria-hidden />
          {t(language, "consent.hear")}
        </button>
      </div>

      {errorMessage && (
        <p className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-red-700">
          <CircleAlert className="size-5 shrink-0" aria-hidden />
          {errorMessage}
        </p>
      )}

      <button
        type="button"
        disabled={consent.isPending}
        onClick={() => consent.mutate(true)}
        className="w-full rounded-2xl bg-emerald-600 py-5 text-xl font-bold text-white disabled:opacity-40"
      >
        {t(language, "consent.grant")}
      </button>
      <button
        type="button"
        disabled={consent.isPending}
        onClick={() => consent.mutate(false)}
        className="w-full rounded-2xl border-2 border-slate-300 py-5 text-xl font-semibold text-slate-600"
      >
        {t(language, "consent.decline")}
      </button>
    </section>
  );
}
