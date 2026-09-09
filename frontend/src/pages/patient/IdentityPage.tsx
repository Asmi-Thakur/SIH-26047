/**
 * P02 — Identity (Phase 2c).
 * Hospital token or walk-in. Submitting creates the backend session
 * (POST /api/sessions) and moves to consent. No Aadhaar/ABHA in this phase.
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CircleAlert, Ticket, UserRound } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { createSession } from "../../services/api";
import { ApiError } from "../../services/api";
import { cn } from "../../utils/cn";
import { t } from "../../utils/i18n";
import { useIntake } from "../../state/sessionStore";

type Mode = "token" | "walkin";

type Department = "general" | "ayush";

export function IdentityPage() {
  const navigate = useNavigate();
  const { language, startSession } = useIntake();
  const [mode, setMode] = useState<Mode>("token");
  const [department, setDepartment] = useState<Department>("general");
  const [token, setToken] = useState("");

  const create = useMutation({
    mutationFn: () =>
      createSession({
        token: mode === "token" && token.trim() ? token.trim() : null,
        language,
        department: department === "ayush" ? "ayush" : null,
        demo: true,
      }),
    onSuccess: (session) => {
      startSession(session.session_id);
      navigate("/patient/consent");
    },
  });

  const canContinue =
    mode === "walkin" || token.trim().length > 0 || create.isPending;
  const errorMessage =
    create.isError && create.error instanceof ApiError
      ? create.error.detail?.message ?? create.error.message
      : create.isError
        ? "Could not start the session."
        : null;

  const optionClass = (active: boolean) =>
    cn(
      "flex w-full items-center gap-4 rounded-2xl border-2 p-5 text-left transition-colors",
      active
        ? "border-indigo-500 bg-indigo-50"
        : "border-slate-200 bg-white hover:border-indigo-300",
    );

  return (
    <section className="mx-auto flex w-full max-w-xl flex-col gap-6 px-4 py-10">
      <h1 className="text-3xl font-bold text-slate-900">
        {t(language, "nav.identity")}
      </h1>
      <p className="text-lg text-slate-600">
        {t(language, "identity.choose")}
      </p>

      <button
        type="button"
        onClick={() => setMode("token")}
        className={optionClass(mode === "token")}
      >
        <Ticket className="size-8 text-indigo-500" aria-hidden />
        <span className="flex flex-col">
          <span className="text-xl font-semibold text-slate-900">
            {t(language, "identity.token")}
          </span>
          <span className="text-slate-500">
            {t(language, "identity.tokenHint")}
          </span>
        </span>
      </button>

      {mode === "token" && (
        <input
          value={token}
          onChange={(e) => setToken(e.target.value)}
          autoFocus
          placeholder={t(language, "identity.tokenPlaceholder")}
          className="w-full rounded-xl border border-slate-300 px-4 py-3 text-xl"
        />
      )}

      <button
        type="button"
        onClick={() => setMode("walkin")}
        className={optionClass(mode === "walkin")}
      >
        <UserRound className="size-8 text-indigo-500" aria-hidden />
        <span className="flex flex-col">
          <span className="text-xl font-semibold text-slate-900">
            {t(language, "identity.walkin")}
          </span>
          <span className="text-slate-500">
            {t(language, "identity.walkinHint")}
          </span>
        </span>
      </button>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          {t(language, "identity.department")}
        </p>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setDepartment("general")}
            className={cn(
              "rounded-xl border-2 px-4 py-3 text-lg font-semibold transition-colors",
              department === "general"
                ? "border-indigo-500 bg-indigo-50 text-indigo-900"
                : "border-slate-200 bg-white text-slate-700",
            )}
          >
            {t(language, "identity.departmentGeneral")}
          </button>
          <button
            type="button"
            onClick={() => setDepartment("ayush")}
            className={cn(
              "rounded-xl border-2 px-4 py-3 text-lg font-semibold transition-colors",
              department === "ayush"
                ? "border-indigo-500 bg-indigo-50 text-indigo-900"
                : "border-slate-200 bg-white text-slate-700",
            )}
          >
            {t(language, "identity.departmentAyush")}
          </button>
        </div>
        <p className="mt-2 text-sm text-slate-500">
          {t(language, "identity.departmentHint")}
        </p>
      </div>

      <div className="rounded-2xl border border-dashed border-slate-300 px-5 py-4 text-slate-400">
        <span className="font-medium">{t(language, "identity.abha")}</span>
        {" — "}
        {t(language, "identity.abhaNote")}
      </div>

      {errorMessage && (
        <p className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-red-700">
          <CircleAlert className="size-5 shrink-0" aria-hidden />
          {errorMessage}
        </p>
      )}

      <button
        type="button"
        disabled={!canContinue}
        onClick={() => create.mutate()}
        className="w-full rounded-2xl bg-indigo-600 py-5 text-xl font-bold text-white disabled:opacity-40"
      >
        {create.isPending
          ? t(language, "identity.creating")
          : t(language, "identity.continue")}
      </button>
    </section>
  );
}
