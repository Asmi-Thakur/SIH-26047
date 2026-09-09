/**
 * Reusable placeholder for Phase 1 screens.
 *
 * Phase 2+ replaces each usage with the real screen implementation. Keeping a
 * shared component avoids duplicating the "not built yet" chrome across the
 * ten route placeholders and gives future screens a consistent skeleton.
 */
import { Construction } from "lucide-react";
import type { ReactNode } from "react";

import { t } from "../../utils/i18n";
import { useLanguage } from "../../state/sessionStore";

interface PlaceholderPageProps {
  /** Screen name, e.g. "Welcome". */
  title: string;
  /** Which build phase implements this screen, e.g. "Phase 2". */
  phase: string;
  /** One-line description of what the finished screen will do. */
  description: string;
  /** Optional extra content below the note (demo hints, links, etc.). */
  children?: ReactNode;
}

export function PlaceholderPage({
  title,
  phase,
  description,
  children,
}: PlaceholderPageProps) {
  const lang = useLanguage();

  return (
    <section className="mx-auto flex w-full max-w-3xl flex-col items-start gap-4 px-4 py-10">
      <div className="flex items-center gap-2">
        <Construction className="size-5 text-slate-400" aria-hidden />
        <h2 className="text-2xl font-semibold text-slate-900">{title}</h2>
        <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700">
          {phase}
        </span>
      </div>

      <p className="text-slate-600">{description}</p>

      <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-500">
        {t(lang, "phase1.placeholderNote")}
      </div>

      {children}
    </section>
  );
}