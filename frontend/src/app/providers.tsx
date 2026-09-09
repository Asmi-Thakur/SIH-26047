/**
 * Application-wide providers.
 *
 * Phase 1 only needs the TanStack Query client. React Query is used for all
 * server state from here on (health checks today, sessions/cases later) so
 * the backend contract stays in services/api.ts and components never fetch
 * directly.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { IntakeProvider } from "../state/sessionStore";

/** retry:false keeps the shell quiet when the backend is down in dev/tests. */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <IntakeProvider>{children}</IntakeProvider>
    </QueryClientProvider>
  );
}