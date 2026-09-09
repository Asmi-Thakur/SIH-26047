/**
 * P01 — Welcome (Phase 2c).
 * Language selection (en/hi) with kiosk-sized targets, then Start.
 */
import { useState } from "react";
import { HeartPulse, Languages } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { cn } from "../../utils/cn";
import type { Language } from "../../utils/i18n";
import { t } from "../../utils/i18n";
import { useIntake } from "../../state/sessionStore";

const languages: Array<{ code: Language; name: string; native: string }> = [
  { code: "en", name: "English", native: "English" },
  { code: "hi", name: "Hindi", native: "हिन्दी" },
];

export function WelcomePage() {
  const navigate = useNavigate();
  const { language, setLanguage } = useIntake();
  const [picked, setPicked] = useState<Language>(language);

  function pick(lang: Language) {
    setPicked(lang);
    setLanguage(lang);
  }

  return (
    <section className="mx-auto flex w-full max-w-2xl flex-col items-center gap-8 px-4 py-12">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="rounded-full bg-indigo-100 p-4">
          <HeartPulse className="size-10 text-indigo-600" aria-hidden />
        </div>
        <h1 className="text-4xl font-bold text-slate-900">
          {t(picked, "appName")}
        </h1>
        <p className="text-lg text-slate-500">
          {t(picked, "nav.welcome")}
        </p>
      </div>

      <div className="flex w-full flex-col gap-3">
        <p className="flex items-center gap-2 text-lg font-medium text-slate-700">
          <Languages className="size-5" aria-hidden />
          {t(picked, "welcome.chooseLanguage")}
        </p>
        {languages.map((lang) => (
          <button
            key={lang.code}
            type="button"
            onClick={() => pick(lang.code)}
            className={cn(
              "flex min-h-20 items-center justify-between rounded-2xl border-2 px-6 text-xl font-semibold transition-colors",
              picked === lang.code
                ? "border-indigo-500 bg-indigo-50 text-indigo-900"
                : "border-slate-200 bg-white text-slate-800 hover:border-indigo-300",
            )}
          >
            <span>{lang.name}</span>
            <span className="text-lg font-normal text-slate-500">
              {lang.native}
            </span>
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={() => navigate("/patient/identity")}
        className="w-full rounded-2xl bg-indigo-600 py-5 text-2xl font-bold text-white shadow-lg shadow-indigo-200 transition-colors hover:bg-indigo-700"
      >
        {t(picked, "welcome.start")}
      </button>
    </section>
  );
}
