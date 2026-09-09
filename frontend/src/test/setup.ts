/**
 * Vitest setup (referenced by vite.config.ts `test.setupFiles`).
 *
 * The app shell polls the backend health endpoint via TanStack Query. In unit
 * tests we stub `fetch` so the HealthBadge resolves deterministically without
 * real network access.
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// Vitest globals are disabled (tests import explicitly), so RTL's automatic
// cleanup never registers — do it here or DOM accumulates across tests.
afterEach(() => {
  cleanup();
});

beforeEach(() => {
  // A Response body can only be consumed once, so build a fresh one per call.
  globalThis.fetch = vi.fn(async () => {
    return new Response(
      JSON.stringify({ status: "ok", service: "medikiosk-backend" }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  });
});