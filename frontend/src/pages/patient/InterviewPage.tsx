/**
 * P05–P06 — Adaptive interview (Phase 2c, touch mode).
 *
 * The backend state machine decides the next question (deterministic, spec
 * §8/§10–12). This screen simply renders each served question and posts the
 * answer; when the machine reports completion we move to the Complete screen.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, LoaderCircle } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { fetchNextQuestion, submitAnswer } from "../../services/api";
import { ApiError } from "../../services/api";
import { QuestionCard } from "../../components/interview/QuestionCard";
import type { AnswerPayload, InterviewQuestion } from "../../types";
import { t } from "../../utils/i18n";
import { useIntake } from "../../state/sessionStore";

const SECTION_ORDER = [
  "chief_complaint",
  "hpi",
  "past_history",
  "medications",
  "allergies",
  "family_history",
  "personal_history",
  "ros",
  "ayush",
];

export function InterviewPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { language, sessionId } = useIntake();

  const [question, setQuestion] = useState<InterviewQuestion | null>(null);
  const [completed, setCompleted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nextQuery = useQuery({
    queryKey: ["interview-next", sessionId],
    queryFn: () => fetchNextQuestion(sessionId!),
    enabled: !!sessionId && !question && !completed,
  });

  useEffect(() => {
    const data = nextQuery.data;
    if (!data) return;
    if (data.completed) {
      setCompleted(true);
    } else {
      setQuestion(data.question);
    }
  }, [nextQuery.data]);

  // Short pause on the final screen before routing to Complete.
  useEffect(() => {
    if (!completed) return;
    const timer = setTimeout(
      () => navigate("/patient/complete", { replace: true }),
      900,
    );
    return () => clearTimeout(timer);
  }, [completed, navigate]);

  const answer = useMutation({
    mutationFn: (payload: AnswerPayload) => submitAnswer(sessionId!, payload),
    onSuccess: (response) => {
      setError(null);
      if (response.completed) {
        setQuestion(null);
        setCompleted(true);
      } else {
        setQuestion(response.question);
      }
    },
    onError: (err: unknown) => {
      const message =
        err instanceof ApiError
          ? err.detail?.message ?? err.message
          : "Could not save your answer.";
      setError(message);
      // A stale or out-of-order question: re-sync from the backend.
      if (err instanceof ApiError && err.detail?.code === "question_not_current") {
        setQuestion(null);
        void queryClient.invalidateQueries({ queryKey: ["interview-next"] });
      }
    },
  });

  if (!sessionId) {
    return (
      <section className="mx-auto max-w-xl px-4 py-10">
        <p className="text-lg text-slate-600">
          Please start from the Welcome screen first.
        </p>
        <Link
          to="/patient/welcome"
          className="mt-4 inline-block text-indigo-600"
        >
          {t(language, "welcome.start")}
        </Link>
      </section>
    );
  }

  if (nextQuery.isPending && !question && !completed) {
    return (
      <section className="mx-auto flex max-w-2xl flex-col items-center gap-4 px-4 py-20 text-slate-500">
        <LoaderCircle className="size-8 animate-spin" aria-hidden />
        <p>{t(language, "interview.loading")}</p>
      </section>
    );
  }

  if (completed || nextQuery.data?.completed) {
    return (
      <section className="mx-auto flex max-w-2xl flex-col items-center gap-4 px-4 py-20 text-center">
        <CircleAlert className="size-10 text-emerald-500" aria-hidden />
        <p className="text-2xl font-semibold text-slate-800">
          {t(language, "interview.done")}
        </p>
      </section>
    );
  }

  const sectionNumber = question ? SECTION_ORDER.indexOf(question.section) + 1 : 0;

  return (
    <section className="mx-auto flex w-full max-w-2xl flex-col gap-5 px-4 py-8">
      {sectionNumber > 0 && (
        <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          {t(language, "interview.sectionOf")} {sectionNumber}/
          {SECTION_ORDER.length}
        </p>
      )}

      {error && (
        <p className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-red-700">
          <CircleAlert className="size-5 shrink-0" aria-hidden />
          {error}
        </p>
      )}

      {question && (
        <QuestionCard
          key={question.question_id}
          question={question}
          language={language}
          disabled={answer.isPending}
          onSubmit={(payload) => answer.mutate(payload)}
        />
      )}
    </section>
  );
}
