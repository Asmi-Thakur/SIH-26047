/**
 * Phase 2c: patient flow over the mocked HTTP API.
 * Welcome -> Identity (create session) -> Consent -> Interview completion.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { routes } from "../../app/router";
import { IntakeProvider } from "../../state/sessionStore";

const SESSION = {
  session_id: "11111111-1111-1111-1111-111111111111",
  patient_id: null,
  case_id: null,
  state: "identity",
  mode: null,
  department: null,
  is_demo: true,
  started_at: "2026-09-07T00:00:00Z",
  completed_at: null,
};

const CONSENT = {
  session_id: SESSION.session_id,
  granted: true,
  purposes: ["clinical_intake"],
  consent_text_version: "v1",
  created_at: "2026-09-07T00:00:00Z",
  revoked_at: null,
};

/** Backend already-complete interview (no question to render). */
const DONE = { state: "documents", completed: true, question: null };

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function fakeBackend(): () => void {
  const calls: string[] = [];

  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const path = url.replace(/^https?:\/\/[^/]+/, "");
    calls.push(path);

    if (path.startsWith("/api/sessions/") && path.endsWith("/consent")) {
      return json(CONSENT);
    }
    if (path.startsWith("/api/interview/") && path.endsWith("/next")) {
      return json(DONE);
    }
    if (path === "/api/sessions" ) {
      return json(SESSION);
    }
    return json({ status: "ok", service: "medikiosk-backend" });
  });

  return () => vi.restoreAllMocks();
}

function renderFlow() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(routes, {
    initialEntries: ["/patient/welcome"],
  });
  render(
    <QueryClientProvider client={queryClient}>
      <IntakeProvider>
        <RouterProvider router={router} />
      </IntakeProvider>
    </QueryClientProvider>,
  );
  return router;
}

beforeEach(() => {
  fakeBackend();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("patient intake flow", () => {
  it("walks Welcome -> Identity -> Consent -> Complete", async () => {
    renderFlow();

    // Welcome: Start (English is the default language).
    fireEvent.click(screen.getByRole("button", { name: "Start" }));

    // Identity: hospital token mode is preselected — type a token, Continue.
    expect(
      await screen.findByRole("button", { name: /Hospital token/i }),
    ).toBeInTheDocument();
    fireEvent.change(
      screen.getByPlaceholderText(/A-104/i),
      { target: { value: "A-777" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));

    // Consent: grant.
    expect(
      await screen.findByRole("button", { name: "I agree — continue" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "I agree — continue" }));

    // Interview reports done -> Complete screen.
    expect(
      await screen.findByText(
        "Your health history has been sent to the clinical team.",
        {},
        { timeout: 2500 },
      ),
    ).toBeInTheDocument();
  });
});
