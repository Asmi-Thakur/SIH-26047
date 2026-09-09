/**
 * Client-side intake state (Phase 2c).
 *
 * Holds the transient kiosk state that is NOT the backend's job: the language
 * the patient picked and the id of the session created for this visit.
 * Server state (questions, answers, consent) lives in TanStack Query and the
 * backend; this context only points at which session to query.
 *
 * The default context value keeps rendering safe when no provider is mounted
 * (e.g. unit tests that only wrap QueryClientProvider).
 */
import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import type { Language } from "../utils/i18n";

export interface IntakeState {
  /** Language chosen on the Welcome screen. */
  language: Language;
  /** Session created for this visit (null until Identity is submitted). */
  sessionId: string | null;
  setLanguage(language: Language): void;
  startSession(sessionId: string): void;
  reset(): void;
}

const defaultState: IntakeState = {
  language: "en",
  sessionId: null,
  setLanguage: () => {},
  startSession: () => {},
  reset: () => {},
};

const IntakeContext = createContext<IntakeState>(defaultState);

export function IntakeProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>("en");
  const [sessionId, setSessionId] = useState<string | null>(null);

  const value = useMemo<IntakeState>(
    () => ({
      language,
      sessionId,
      setLanguage,
      startSession: setSessionId,
      reset: () => setSessionId(null),
    }),
    [language, sessionId],
  );

  return <IntakeContext.Provider value={value}>{children}</IntakeContext.Provider>;
}

export function useIntake(): IntakeState {
  return useContext(IntakeContext);
}

/** Convenience hook used by the shell and pages for translated strings. */
export function useLanguage(): Language {
  return useIntake().language;
}
