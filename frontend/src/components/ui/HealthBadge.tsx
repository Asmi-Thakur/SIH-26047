/**
 * Backend connectivity badge shown in the app shell.
 *
 * Uses TanStack Query with retry disabled (see providers.tsx) so the UI never
 * blocks or spams the network when the backend is down during development.
 */
import { useQuery } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";

import { checkHealth } from "../../services/api";
import { t } from "../../utils/i18n";
import { useLanguage } from "../../state/sessionStore";

export function HealthBadge() {
  const lang = useLanguage();
  const { isPending, isSuccess } = useQuery({
    queryKey: ["health"],
    queryFn: checkHealth,
    refetchInterval: 30_000,
  });

  if (isPending) {
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600"
        title={t(lang, "backend.checking")}
      >
        <LoaderCircle className="size-3.5 animate-spin" />
        {t(lang, "backend.checking")}
      </span>
    );
  }

  if (isSuccess) {
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs text-emerald-700"
        title={t(lang, "backend.connected")}
      >
        <CircleCheck className="size-3.5" />
        {t(lang, "backend.connected")}
      </span>
    );
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-xs text-red-700"
      title={t(lang, "backend.unreachable")}
    >
      <CircleAlert className="size-3.5" />
      {t(lang, "backend.unreachable")}
    </span>
  );
}