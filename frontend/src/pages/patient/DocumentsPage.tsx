/**
 * P07–P08 — Documents (Phase 4/2).
 *
 * Upload prior documents (the kiosk camera exposes itself as a file input),
 * then run OCR + extraction through POST /documents/{id}/reprocess. The
 * processing stages (spec P08) map to the document's real processing_status;
 * extracted abnormal values are shown with their provenance. Mock OCR is
 * always labelled "simulated" — never presented as real OCR (honesty rule).
 */
import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  FileWarning,
  LoaderCircle,
  ScanText,
  Sparkles,
  Upload,
} from "lucide-react";
import { useRef, useState } from "react";

import { reprocessDocument } from "../../services/api";
import { useIntake, useLanguage } from "../../state/sessionStore";
import { t } from "../../utils/i18n";
import type { DocumentReprocessResponse } from "../../types";

const API_BASE: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function StatusStages({ status }: { status: string }) {
  const lang = useLanguage();
  const stages = [
    { key: "received", label: t(lang, "documents.stage.received"), done: true, active: false },
    {
      key: "ocr",
      label: t(lang, "documents.stage.ocr"),
      done: status === "completed" || status === "failed",
      active: status === "processing",
    },
    {
      key: "extracted",
      label: t(lang, "documents.stage.extracted"),
      done: status === "completed" || status === "failed",
      active: status === "processing",
    },
    {
      key: "values",
      label: t(lang, "documents.stage.values"),
      done: status === "completed",
      active: status === "processing",
    },
  ];

  return (
    <ol className="flex flex-col gap-2 text-lg">
      {stages.map((stage) => (
        <li key={stage.key} className="flex items-center gap-3">
          {stage.done ? (
            <span className="text-emerald-600">✓</span>
          ) : stage.active ? (
            <LoaderCircle className="size-5 animate-spin text-sky-600" />
          ) : (
            <span className="text-slate-300">○</span>
          )}
          <span className={stage.done ? "text-slate-700" : "text-slate-400"}>
            {stage.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

function ResultCard({ result }: { result: DocumentReprocessResponse }) {
  const lang = useLanguage();
  const extraction = result.extraction;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm">
      <div className="flex items-center gap-3">
        <ScanText className="size-8 text-emerald-600" aria-hidden />
        <div>
          <p className="text-xl font-semibold text-slate-900">
            {extraction?.document_type_label ??
              t(lang, "documents.result.document")}
          </p>
          <p className="text-sm text-slate-500">
            {result.page_count} {t(lang, "documents.result.pages")} ·{" "}
            {t(lang, "documents.result.confidence")}{" "}
            {result.confidence != null
              ? `${Math.round(result.confidence * 100)}%`
              : "—"}
          </p>
        </div>
        {result.ocr_mocked ? (
          <span className="ml-auto rounded-full bg-amber-100 px-3 py-1 text-sm font-medium text-amber-800">
            {t(lang, "documents.result.mockLabel")}
          </span>
        ) : (
          <span className="ml-auto rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-800">
            {t(lang, "documents.result.realLabel")}
          </span>
        )}
      </div>

      {result.status === "failed" ? (
        <div className="mt-4 flex items-start gap-3 rounded-xl bg-red-50 p-4 text-red-800">
          <FileWarning className="mt-1 size-5 shrink-0" aria-hidden />
          <div>
            <p className="font-semibold">{t(lang, "documents.result.failed")}</p>
            <p className="text-sm">{result.error ?? ""}</p>
          </div>
        </div>
      ) : (
        extraction && (
          <>
            {extraction.abnormal_values.length > 0 && (
              <div className="mt-4 rounded-xl bg-amber-50 p-4">
                <p className="flex items-center gap-2 font-semibold text-amber-900">
                  <AlertTriangle className="size-5" aria-hidden />
                  {t(lang, "documents.result.abnormal")}
                </p>
                <ul className="mt-2 space-y-1 text-lg text-amber-900">
                  {extraction.abnormal_values.map((v) => (
                    <li key={`${v.name}-${v.value}`}>
                      <strong>
                        {v.name} {v.value} {v.unit}
                      </strong>{" "}
                      — {v.status.toUpperCase()}
                      {v.reference_low != null && v.reference_high != null
                        ? ` (${t(lang, "documents.result.reference")}: ${v.reference_low}–${v.reference_high})`
                        : ""}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {extraction.medications.length > 0 && (
              <div className="mt-3 text-lg text-slate-700">
                <p className="font-semibold text-slate-900">
                  {t(lang, "documents.result.medications")}
                </p>
                <ul className="list-inside list-disc">
                  {extraction.medications.map((m) => (
                    <li key={m.name}>
                      {m.name}
                      {m.strength ? ` — ${m.strength}` : ""}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {extraction.conditions.length > 0 && (
              <p className="mt-3 text-lg text-slate-700">
                <span className="font-semibold text-slate-900">
                  {t(lang, "documents.result.conditions")}:{" "}
                </span>
                {extraction.conditions.map((c) => c.text).join(", ")}
              </p>
            )}

            <p className="mt-4 text-xs text-slate-400">{extraction.engine_note}</p>
          </>
        )
      )}
    </section>
  );
}

export function DocumentsPage() {
  const { language, sessionId } = useIntake();
  const imageInput = useRef<HTMLInputElement>(null);
  const pdfInput = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<DocumentReprocessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: async (file: File) => {
      if (!sessionId) throw new Error("no-session");
      const form = new FormData();
      form.append("session_id", sessionId);
      form.append("file", file);
      // Multipart upload: deliberately not the JSON request helper.
      const response = await fetch(`${API_BASE}/api/documents/upload`, {
        method: "POST",
        body: form,
      });
      if (!response.ok) throw new Error(`upload-failed-${response.status}`);
      return (await response.json()) as { document_id: string };
    },
    onSuccess: async (doc) => {
      setError(null);
      try {
        const processed = await reprocessDocument(doc.document_id);
        setResult(processed);
      } catch (err) {
        setError(err instanceof Error ? err.message : "reprocess-failed");
      }
    },
    onError: () => setError("upload-failed"),
  });

  const skip = () => {
    // P07 "Skip": continue without documents — the deterministic shell stays usable.
    window.location.assign("/patient/review");
  };

  const busy = upload.isPending || (result === null && error === null && upload.isSuccess);

  return (
    <section className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-10">
      <header className="text-center">
        <h1 className="text-3xl font-bold text-slate-900">
          {t(language, "nav.documents")}
        </h1>
        <p className="mt-1 text-xl text-slate-600">
          {t(language, "documents.prompt")}
        </p>
      </header>

      <input
        ref={imageInput}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload.mutate(file);
        }}
      />
      <input
        ref={pdfInput}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload.mutate(file);
        }}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <button
          type="button"
          onClick={() => imageInput.current?.click()}
          disabled={upload.isPending}
          className="flex min-h-28 flex-col items-center justify-center gap-2 rounded-2xl bg-sky-600 px-6 py-6 text-2xl font-semibold text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-60"
        >
          <Upload className="size-8" aria-hidden />
          {t(language, "documents.uploadImage")}
        </button>
        <button
          type="button"
          onClick={() => pdfInput.current?.click()}
          disabled={upload.isPending}
          className="flex min-h-28 flex-col items-center justify-center gap-2 rounded-2xl bg-sky-600 px-6 py-6 text-2xl font-semibold text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-60"
        >
          <Upload className="size-8" aria-hidden />
          {t(language, "documents.uploadPdf")}
        </button>
        <button
          type="button"
          onClick={skip}
          disabled={upload.isPending}
          className="flex min-h-28 flex-col items-center justify-center gap-2 rounded-2xl border-2 border-slate-300 bg-white px-6 py-6 text-2xl font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
        >
          {t(language, "interview.skip")}
          <ArrowRight className="size-8" aria-hidden />
        </button>
      </div>

      {busy && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <StatusStages status="processing" />
        </div>
      )}

      {error && (
        <div className="flex items-start gap-3 rounded-xl bg-red-50 p-4 text-red-800">
          <FileWarning className="mt-1 size-5 shrink-0" aria-hidden />
          <p>{t(language, "documents.error")}</p>
        </div>
      )}

      {result && <ResultCard result={result} />}

      {result && result.status === "completed" && (
        <button
          type="button"
          onClick={() => window.location.assign("/patient/review")}
          className="mx-auto flex items-center gap-2 rounded-2xl bg-emerald-600 px-10 py-5 text-2xl font-semibold text-white shadow-sm transition hover:bg-emerald-700"
        >
          <Sparkles className="size-6" aria-hidden />
          {t(language, "documents.continue")}
        </button>
      )}
    </section>
  );
}
