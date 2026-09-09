/**
 * Physician case review (Phase 6) — AI draft → edit → verify → confirm.
 *
 * The route param is the *session* id (the queue links to
 * /doctor/case/:sessionId); the backend get-or-creates the unified case and
 * returns the canonical machine-readable case plus the editable summary
 * draft. The doctor edits the text sections, saves a draft (PATCH, versioned)
 * and confirms the clinical record (POST), which locks it and gates FHIR
 * export. AI content is always labelled — it never overwrites confirmed data.
 */
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  LoaderCircle,
  Lock,
  Save,
  Share2,
  ShieldAlert,
  Stethoscope,
} from "lucide-react";

import { cn } from "../../utils/cn";
import {
  confirmCase,
  exportFhir,
  fetchCaseBySession,
  patchCaseSummary,
} from "../../services/api";
import { useLanguage } from "../../state/sessionStore";
import { t, type Language } from "../../utils/i18n";
import type { TranslationKey } from "../../i18n/en";

const SECTION_ORDER: string[] = [
  "patient_encounter",
  "chief_complaint",
  "history_of_present_illness",
  "past_medical_history",
  "past_surgical_history",
  "medications",
  "allergies",
  "family_history",
  "personal_social_history",
  "review_of_systems",
  "ayush_history",
  "prior_investigations",
  "timeline",
  "triage_status",
  "missing_uncertain_information",
];

const SECTION_LABEL_KEYS: Record<string, TranslationKey> = {
  patient_encounter: "case.section.patient_encounter",
  chief_complaint: "case.section.chief_complaint",
  history_of_present_illness: "case.section.history_of_present_illness",
  past_medical_history: "case.section.past_medical_history",
  past_surgical_history: "case.section.past_surgical_history",
  medications: "case.section.medications",
  allergies: "case.section.allergies",
  family_history: "case.section.family_history",
  personal_social_history: "case.section.personal_social_history",
  review_of_systems: "case.section.review_of_systems",
  ayush_history: "case.section.ayush_history",
  prior_investigations: "case.section.prior_investigations",
  timeline: "case.section.timeline",
  triage_status: "case.section.triage_status",
  missing_uncertain_information: "case.section.missing_uncertain_information",
};

function statusLabel(lang: Language, status: string): string {
  if (status === "confirmed") return t(lang, "case.status.confirmed");
  if (status === "physician_edited") return t(lang, "case.status.physician_edited");
  return t(lang, "case.status.draft");
}

function StatusBadge({ status }: { status: string }) {
  const lang = useLanguage();
  const palette =
    status === "confirmed"
      ? "bg-emerald-100 text-emerald-800"
      : status === "physician_edited"
        ? "bg-amber-100 text-amber-800"
        : "bg-slate-100 text-slate-700";
  return (
    <span className={cn("rounded-full px-3 py-1 text-xs font-semibold", palette)}>
      {statusLabel(lang, status)}
    </span>
  );
}

export function CasePage() {
  const { caseId } = useParams<{ caseId: string }>();
  const lang = useLanguage();

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => fetchCaseBySession(caseId ?? ""),
    enabled: Boolean(caseId),
  });

  const [draft, setDraft] = useState<Record<string, string> | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmArmed, setConfirmArmed] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) setDraft(data.summary);
  }, [data]);

  const canonical = data?.canonical;
  const patient = canonical?.patient;
  const urgent = canonical?.triage?.priority === "urgent";
  const confirmed = data?.status === "confirmed";

  const timeline = useMemo(() => canonical?.timeline ?? [], [canonical]);
  const documents = canonical?.documents ?? [];
  const missing = canonical?.missing_information ?? [];

  async function handleSave() {
    if (!data || !draft) return;
    setSaving(true);
    setError(null);
    try {
      await patchCaseSummary(data.case_id, { summary: draft });
      setNotice(t(lang, "case.saved"));
      await refetch();
    } catch {
      setError(t(lang, "case.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  async function handleConfirm() {
    if (!data) return;
    if (!confirmArmed) {
      setConfirmArmed(true);
      return;
    }
    setConfirming(true);
    setError(null);
    try {
      await confirmCase(data.case_id);
      setNotice(t(lang, "case.confirmed"));
      setConfirmArmed(false);
      await refetch();
    } catch {
      setError(t(lang, "case.confirmFailed"));
    } finally {
      setConfirming(false);
    }
  }

  async function handleExport() {
    if (!data) return;
    setExporting(true);
    setError(null);
    try {
      const result = await exportFhir(data.case_id);
      if (result.status === "succeeded") {
        const entries = Array.isArray(
          (result.bundle as { entry?: unknown[] } | null)?.entry,
        )
          ? (result.bundle as { entry: unknown[] }).entry.length
          : 0;
        setNotice(
          entries > 0
            ? `${t(lang, "case.exportSucceeded")} — ${entries} resources`
            : t(lang, "case.exportSucceeded"),
        );
      } else {
        setError(`${t(lang, "case.exportFailed")} ${result.error ?? ""}`.trim());
      }
    } catch {
      setError(t(lang, "case.exportFailed"));
    } finally {
      setExporting(false);
    }
  }

  if (isPending) {
    return (
      <section className="mx-auto flex w-full max-w-3xl items-center gap-2 px-4 py-12 text-slate-500">
        <LoaderCircle className="size-5 animate-spin" aria-hidden />
        {t(lang, "case.loading")}
      </section>
    );
  }

  if (isError || !data) {
    return (
      <section className="mx-auto flex w-full max-w-3xl flex-col items-start gap-3 px-4 py-12">
        <p className="text-slate-700">{t(lang, "case.error")}</p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {t(lang, "case.retry")}
        </button>
      </section>
    );
  }

  const consentLabel = canonical?.consent?.granted
    ? t(lang, "case.consent.granted")
    : canonical?.consent
      ? t(lang, "case.consent.declined")
      : t(lang, "case.consent.none");

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">
            {patient?.token ?? t(lang, "nav.case")}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {[patient?.age ? `${patient.age} y` : null, consentLabel]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={data.status} />
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
            {t(lang, "case.version")}
            {data.draft_version}
          </span>
        </div>
      </div>

      {/* Triage banner */}
      {urgent && (
        <div className="flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-red-800">
          <ShieldAlert className="size-6 shrink-0" aria-hidden />
          <p className="text-sm font-semibold">{t(lang, "case.urgent")}</p>
        </div>
      )}

      {/* Editable summary sections */}
      <div className="flex flex-col gap-4">
        {(draft ? SECTION_ORDER : []).map((key) => (
          <div
            key={key}
            className="rounded-2xl border border-slate-200 bg-white p-5"
          >
            <label
              htmlFor={`case-${key}`}
              className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-800"
            >
              <FileText className="size-4 text-indigo-400" aria-hidden />
              {t(lang, SECTION_LABEL_KEYS[key])}
            </label>
            <textarea
              id={`case-${key}`}
              value={draft?.[key] ?? ""}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...(prev ?? {}),
                  [key]: event.target.value,
                }))
              }
              disabled={confirmed}
              rows={key === "timeline" ? 6 : 3}
              className="w-full resize-y rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-sm leading-relaxed text-slate-800 focus:border-indigo-400 focus:bg-white focus:outline-none disabled:opacity-70"
            />
          </div>
        ))}
      </div>

      {/* Documents + timeline + missing info */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-800">
            <FileText className="size-4 text-indigo-400" aria-hidden />
            {t(lang, "case.documents")}
          </h2>
          {documents.length === 0 ? (
            <p className="text-sm text-slate-500">{t(lang, "case.documentsEmpty")}</p>
          ) : (
            <ul className="flex flex-col gap-2 text-sm text-slate-700">
              {documents.map((doc) => (
                <li key={doc.document_id}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium">{doc.file_name}</span>
                    <span className="shrink-0 text-xs text-slate-400">
                      {doc.processing_status}
                      {doc.ocr_provider ? ` · ${doc.ocr_provider}` : ""}
                      {doc.ocr_mocked ? ` · ${t(lang, "case.ocrMocked")}` : ""}
                    </span>
                  </div>
                  {(doc.abnormal_values ?? []).length > 0 && (
                    <ul className="mt-1 list-inside list-disc text-xs text-amber-700">
                      {(doc.abnormal_values ?? []).map((flag) => (
                        <li key={`${flag.name}-${flag.value}`}>
                          {flag.name} {flag.value} {flag.unit} —{" "}
                          {flag.status.toUpperCase()} [document_extracted]
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-800">
            <AlertTriangle className="size-4 text-amber-500" aria-hidden />
            {t(lang, "case.missing")}
          </h2>
          {missing.length === 0 ? (
            <p className="text-sm text-slate-500">—</p>
          ) : (
            <ul className="flex list-inside list-disc flex-col gap-1 text-sm text-slate-700">
              {missing.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Timeline */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-800">
          <Stethoscope className="size-4 text-indigo-400" aria-hidden />
          {t(lang, "case.timeline")}
        </h2>
        <ol className="flex flex-col gap-1.5 text-sm text-slate-700">
          {timeline.map((event, index) => (
            <li key={index} className="flex gap-2">
              <span className="shrink-0 font-mono text-xs text-slate-400">
                {new Date(event.at ?? "").toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
              <span className="min-w-0">
                <span className="font-medium capitalize">{event.kind}</span> —{" "}
                <span className="text-slate-500">{event.label}</span>
                {event.detail ? ` — ${event.detail}` : ""}
              </span>
            </li>
          ))}
        </ol>
      </div>

      {/* Actions */}
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        {t(lang, "case.disclaimer")}
      </div>

      {notice && <p className="text-sm font-medium text-emerald-700">{notice}</p>}
      {error && <p className="text-sm font-medium text-red-700">{error}</p>}
      {confirmed && (
        <p className="text-xs text-slate-500">{t(lang, "case.exportDestination")}</p>
      )}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving || confirmed}
          className="flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-slate-800 ring-1 ring-slate-300 hover:bg-slate-50 disabled:opacity-50"
        >
          <Save className="size-4" aria-hidden />
          {t(lang, "case.saveDraft")}
        </button>
        <button
          type="button"
          onClick={() => void handleExport()}
          disabled={!confirmed || exporting}
          title={confirmed ? undefined : t(lang, "case.exportBlocked")}
          className="flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-slate-800 ring-1 ring-slate-300 hover:bg-slate-50 disabled:opacity-50"
        >
          {exporting ? (
            <LoaderCircle className="size-4 animate-spin" aria-hidden />
          ) : (
            <Share2 className="size-4" aria-hidden />
          )}
          {exporting ? t(lang, "case.exporting") : t(lang, "case.export")}
        </button>
        <button
          type="button"
          onClick={() => void handleConfirm()}
          disabled={confirming || confirmed}
          className={cn(
            "flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50",
            confirmArmed
              ? "bg-red-600 hover:bg-red-700"
              : "bg-emerald-600 hover:bg-emerald-700",
          )}
        >
          {confirmed ? (
            <>
              <CheckCircle2 className="size-4" aria-hidden />
              {t(lang, "case.status.confirmed")}
            </>
          ) : confirmArmed ? (
            <>
              <Lock className="size-4" aria-hidden />
              {t(lang, "case.confirmAsk")}
            </>
          ) : (
            <>
              <Lock className="size-4" aria-hidden />
              {t(lang, "case.confirm")}
            </>
          )}
        </button>
      </div>
    </section>
  );
}