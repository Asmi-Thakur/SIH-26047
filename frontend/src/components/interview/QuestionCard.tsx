/**
 * Touch question card (Phase 2c + 3d).
 *
 * Behaviour by input type:
 *   choice -> tap a choice to submit immediately
 *   multi  -> toggle choices, then Confirm
 *   text   -> "Type" (textarea) or "Speak" (MediaRecorder -> transcribe ->
 *             confirm transcript as the answer). Voice degrades gracefully:
 *             if recording is unsupported/permission denied/transcribe fails,
 *             the patient can always type instead (spec §60).
 * allow_other appends an "Other" chip that reveals a free-text field.
 */
import { useState } from "react";
import {
  Check,
  Keyboard,
  LoaderCircle,
  Mic,
  RotateCcw,
  Square,
} from "lucide-react";

import { useRecorder } from "../../hooks/useRecorder";
import { transcribeAudio, SpeechError } from "../../services/speech";
import type { AnswerPayload, InterviewQuestion } from "../../types";
import { cn } from "../../utils/cn";
import type { Language } from "../../utils/i18n";
import { t } from "../../utils/i18n";

interface QuestionCardProps {
  question: InterviewQuestion;
  language: Language;
  disabled?: boolean;
  onSubmit(payload: AnswerPayload): void;
}

type TextTab = "type" | "speak";

export function QuestionCard({
  question,
  language,
  disabled,
  onSubmit,
}: QuestionCardProps) {
  const [picked, setPicked] = useState<string[]>([]);
  const [otherText, setOtherText] = useState("");
  const [textValue, setTextValue] = useState("");
  const [tab, setTab] = useState<TextTab>("type");

  const recorder = useRecorder();
  const [transcribing, setTranscribing] = useState(false);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [speakError, setSpeakError] = useState<string | null>(null);

  const prompt =
    language === "hi" && question.prompt_hi
      ? question.prompt_hi
      : question.prompt_en;

  const isTextInput = question.input === "text";

  function label(code: string, fallback: string): string {
    const choice = question.choices.find((c) => c.code === code);
    if (choice) {
      return language === "hi" && choice.label_hi
        ? choice.label_hi
        : choice.label_en;
    }
    return fallback;
  }

  function toggle(code: string) {
    setPicked((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  }

  function pickChoice(code: string) {
    if (code === "other") {
      setPicked([code]);
      return;
    }
    onSubmit({ question_id: question.question_id, choice_codes: [code] });
  }

  function submitText() {
    onSubmit({ question_id: question.question_id, text: textValue.trim() });
  }

  function submitTranscript() {
    if (transcript) {
      onSubmit({ question_id: question.question_id, text: transcript });
    }
  }

  const otherPicked = picked.includes("other");

  function submitMulti() {
    onSubmit({
      question_id: question.question_id,
      choice_codes: picked,
      text: otherPicked && otherText ? otherText : undefined,
    });
  }

  async function handleRecordStop() {
    const blob = await recorder.stop();
    if (!blob) return;
    setTranscribing(true);
    setSpeakError(null);
    try {
      const result = await transcribeAudio(blob, language);
      setTranscript(result.transcript);
      setTab("speak");
    } catch (err) {
      setSpeakError(
        err instanceof SpeechError ? err.message : t(language, "interview.speakTranscribeError"),
      );
    } finally {
      setTranscribing(false);
    }
  }

  const speakDisabled = disabled || recorder.recording || transcribing;

  return (
    <div className="flex w-full flex-col gap-6">
      <p className="text-2xl font-semibold leading-snug text-slate-900">
        {prompt}
      </p>

      {isTextInput && (
        <>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setTab("type")}
              className={cn(
                "inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-base font-semibold transition-colors",
                tab === "type"
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200",
              )}
            >
              <Keyboard className="size-4" aria-hidden />
              {t(language, "interview.tabType")}
            </button>
            <button
              type="button"
              onClick={() => setTab("speak")}
              className={cn(
                "inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-base font-semibold transition-colors",
                tab === "speak"
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200",
              )}
            >
              <Mic className="size-4" aria-hidden />
              {t(language, "interview.tabSpeak")}
            </button>
          </div>

          {tab === "type" ? (
            <div className="flex flex-col gap-3">
              <textarea
                value={textValue}
                onChange={(e) => setTextValue(e.target.value)}
                rows={3}
                placeholder={t(language, "interview.typeHere")}
                className="w-full rounded-xl border border-slate-300 p-4 text-lg"
              />
              <div className="flex gap-3">
                <button
                  type="button"
                  disabled={disabled || textValue.trim().length === 0}
                  onClick={submitText}
                  className="rounded-2xl bg-indigo-600 px-8 py-4 text-lg font-semibold text-white disabled:opacity-40"
                >
                  {t(language, "interview.continue")}
                </button>
                {!question.required && (
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={submitText}
                    className="rounded-2xl border border-slate-300 px-8 py-4 text-lg font-medium text-slate-600"
                  >
                    {t(language, "interview.skip")}
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-5">
              {!recorder.supported && (
                <p className="text-slate-600">
                  {t(language, "interview.speakUnsupported")}
                </p>
              )}
              {recorder.supported && recorder.error === "permission" && (
                <p className="text-slate-600">
                  {t(language, "interview.speakError")}
                </p>
              )}
              {recorder.supported && speakError && (
                <p className="text-red-700">{speakError}</p>
              )}

              {recorder.recording && (
                <div className="flex items-center gap-3">
                  <span className="relative flex size-3">
                    <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-75" />
                    <span className="relative inline-flex size-3 rounded-full bg-red-500" />
                  </span>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => void handleRecordStop()}
                    className="inline-flex items-center gap-2 rounded-2xl bg-red-600 px-6 py-3.5 text-lg font-semibold text-white"
                  >
                    <Square className="size-4" aria-hidden />
                    {t(language, "interview.speakStop")}
                  </button>
                </div>
              )}

              {!recorder.recording &&
                !transcribing &&
                !transcript &&
                recorder.supported &&
                !speakError && (
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => void recorder.start()}
                    className="inline-flex items-center gap-2 self-start rounded-2xl bg-indigo-600 px-6 py-3.5 text-lg font-semibold text-white"
                  >
                    <Mic className="size-5" aria-hidden />
                    {t(language, "interview.speakStart")}
                  </button>
                )}

              {transcribing && (
                <div className="flex items-center gap-2 text-slate-600">
                  <LoaderCircle className="size-5 animate-spin" aria-hidden />
                  {t(language, "interview.speakTranscribing")}
                </div>
              )}

              {transcript && (
                <div className="flex flex-col gap-3">
                  <p className="text-sm font-semibold uppercase tracking-wide text-slate-400">
                    {t(language, "interview.speakPreview")}
                  </p>
                  <p className="rounded-xl bg-white p-4 text-lg text-slate-900">
                    {transcript}
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      disabled={speakDisabled}
                      onClick={submitTranscript}
                      className="rounded-2xl bg-emerald-600 px-6 py-3 font-semibold text-white disabled:opacity-40"
                    >
                      {t(language, "interview.speakUse")}
                    </button>
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => {
                        setTranscript(null);
                        setSpeakError(null);
                        void recorder.start();
                      }}
                      className="inline-flex items-center gap-2 rounded-2xl border border-slate-300 px-6 py-3 font-medium text-slate-600"
                    >
                      <RotateCcw className="size-4" aria-hidden />
                      {t(language, "interview.speakAgain")}
                    </button>
                  </div>
                </div>
              )}

              <button
                type="button"
                disabled={disabled}
                onClick={() => setTab("type")}
                className="self-start text-sm font-medium text-slate-500 underline"
              >
                {t(language, "interview.speakBack")}
              </button>
            </div>
          )}
        </>
      )}

      {!isTextInput && (
        <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
          {(question.choices ?? []).map((choice) => {
            const active =
              question.input === "choice"
                ? picked[0] === choice.code
                : picked.includes(choice.code);
            return (
              <button
                key={choice.code}
                type="button"
                disabled={disabled}
                onClick={() =>
                  question.input === "multi"
                    ? toggle(choice.code)
                    : pickChoice(choice.code)
                }
                className={cn(
                  "flex min-h-16 items-center justify-between gap-2 rounded-2xl border-2 px-5 py-4 text-left text-lg font-medium transition-colors",
                  active
                    ? "border-indigo-500 bg-indigo-50 text-indigo-900"
                    : "border-slate-200 bg-white text-slate-800 hover:border-indigo-300 hover:bg-indigo-50/40",
                )}
              >
                {label(choice.code, choice.code)}
                {active && <Check className="size-5 shrink-0" aria-hidden />}
              </button>
            );
          })}
          {question.allow_other && (
            <button
              type="button"
              disabled={disabled}
              onClick={() =>
                question.input === "multi" ? toggle("other") : pickChoice("other")
              }
              className={cn(
                "flex min-h-16 items-center justify-between gap-2 rounded-2xl border-2 border-dashed px-5 py-4 text-left text-lg font-medium",
                otherPicked
                  ? "border-indigo-500 bg-indigo-50 text-indigo-900"
                  : "border-slate-300 text-slate-600 hover:border-indigo-300",
              )}
            >
              {t(language, "interview.other")}
              {otherPicked && <Check className="size-5 shrink-0" aria-hidden />}
            </button>
          )}
        </div>
      )}

      {!isTextInput && otherPicked && (
        <div className="flex flex-col gap-3">
          <textarea
            value={otherText}
            onChange={(e) => setOtherText(e.target.value)}
            rows={2}
            placeholder={t(language, "interview.typeHere")}
            className="w-full rounded-xl border border-slate-300 p-4 text-lg"
          />
          <button
            type="button"
            disabled={disabled || otherText.trim().length === 0}
            onClick={submitMulti}
            className="self-start rounded-2xl bg-indigo-600 px-8 py-4 text-lg font-semibold text-white disabled:opacity-40"
          >
            {t(language, "interview.confirm")}
          </button>
        </div>
      )}

      {question.input === "multi" && !otherPicked && (
        <button
          type="button"
          disabled={disabled || picked.length === 0}
          onClick={submitMulti}
          className="self-start rounded-2xl bg-indigo-600 px-8 py-4 text-lg font-semibold text-white disabled:opacity-40"
        >
          {t(language, "interview.confirm")}
        </button>
      )}
    </div>
  );
}
