/**
 * P09 — Patient confirmation (Phase 4/2 judging polish).
 *
 * Plain-language confirmation of what will reach the clinical team: chief
 * complaint, medicines, allergies and uploaded documents (with their OCR
 * status). The patient can go back and edit; Continue closes the intake.
 * Read-only over the unified case — no AI text is authored here.
 */
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, FileText, LoaderCircle, Pill, ShieldAlert } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { fetchCaseBySession } from "../../services/api";
import { useIntake } from "../../state/sessionStore";
import { t } from "../../utils/i18n";

export function ReviewPage() {
  const navigate = useNavigate();
  const { language, sessionId } = useIntake();

  const caseQuery = useQuery({
    queryKey: ["case", sessionId],
    queryFn: () => fetchCaseBySession(sessionId!),
    enabled: !!sessionId,
  });

  if (!sessionId) {
    return (
      <section className="mx-auto max-w-xl px-4 py-10">
        <p className="text-lg text-slate-600">
          Please start from the Welcome screen first.
        </p>
        <Link to="/patient/welcome" className="mt-4 inline-block text-indigo-600">
          {t(language, "welcome.start")}
        </Link>
      </section>
    );
  }

  if (caseQuery.isPending) {
    return (
      <section className="mx-auto flex max-w-xl flex-col items-center gap-4 px-4 py-16">
        <LoaderCircle className="size-8 animate-spin text-indigo-500" aria-hidden />
        <p className="text-lg text-slate-600">{t(language, "review.loading")}</p>
      </section>
    );
  }

  const canonical = caseQuery.data?.canonical;
  const complaint = canonical?.chief_complaint?.text;
  const medications = (canonical?.medications?.list ?? [])
    .map((item) => item.text)
    .filter(Boolean);
  const allergies = (canonical?.allergies ?? [])
    .map((item) => item.text)
    .filter((text) => text && !/^no medicine allergy$/i.test(text));
  const documents = canonical?.documents ?? [];

  return (
    <section className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-10">
      <header className="text-center">
        <h1 className="text-3xl font-bold text-slate-900">{t(language, "nav.review")}</h1>
        <p className="mt-1 text-xl text-slate-600">{t(language, "review.prompt")}</p>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm">
        <p className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <CheckCircle2 className="size-6 text-emerald-500" aria-hidden />
          {t(language, "review.complaint")}
        </p>
        <p className="mt-2 text-2xl text-slate-800">{complaint ?? t(language, "review.notRecorded")}</p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm">
        <p className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <Pill className="size-6 text-indigo-500" aria-hidden />
          {t(language, "review.medicines")}
        </p>
        {medications.length > 0 ? (
          <ul className="mt-2 list-inside list-disc text-xl text-slate-800">
            {medications.map((med) => (
              <li key={med}>{med}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xl text-slate-500">{t(language, "review.none")}</p>
        )}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm">
        <p className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <ShieldAlert className="size-6 text-amber-500" aria-hidden />
          {t(language, "review.allergies")}
        </p>
        {allergies.length > 0 ? (
          <ul className="mt-2 list-inside list-disc text-xl text-slate-800">
            {allergies.map((allergy) => (
              <li key={allergy}>{allergy}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xl text-slate-500">{t(language, "review.none")}</p>
        )}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm">
        <p className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <FileText className="size-6 text-sky-500" aria-hidden />
          {t(language, "review.documents")}
        </p>
        {documents.length > 0 ? (
          <ul className="mt-2 space-y-1 text-xl text-slate-800">
            {documents.map((doc) => (
              <li key={doc.document_id}>
                {doc.file_name}
                {doc.processing_status === "completed" ? " ✓" : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xl text-slate-500">{t(language, "review.noDocuments")}</p>
        )}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <Link
          to="/patient/interview"
          className="flex-1 rounded-2xl border-2 border-slate-300 bg-white py-4 text-center text-xl font-semibold text-slate-700 hover:bg-slate-50"
        >
          {t(language, "review.edit")}
        </Link>
        <button
          type="button"
          onClick={() => navigate("/patient/complete")}
          className="flex flex-[2] items-center justify-center gap-2 rounded-2xl bg-emerald-600 py-4 text-xl font-bold text-white hover:bg-emerald-700"
        >
          {t(language, "review.submit")}
          <ArrowRight className="size-6" aria-hidden />
        </button>
      </div>
    </section>
  );
}
