/**
 * Phase 6: physician case review — renders the AI draft, saves edits (PATCH)
 * and confirms the record (POST).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { routes } from "../../app/router";
import { IntakeProvider } from "../../state/sessionStore";

const SESSION_ID = "22222222-2222-2222-2222-222222222222";
const CASE_ID = "33333333-3333-3333-3333-333333333333";

const CASE: Record<string, unknown> = {
  case_id: CASE_ID,
  session_id: SESSION_ID,
  status: "draft",
  draft_version: 1,
  updated_at: "2026-09-08T00:00:00Z",
  confirmed_at: null,
  canonical: {
    session_id: SESSION_ID,
    patient: { token: "A-900", age: 52, preferred_language: "en" },
    consent: { granted: true, purposes: [], timestamp: "2026-09-08T00:00:00Z" },
    chief_complaint: { code: "chest_pain", text: "Chest pain", onset: "1–3 days ago", source: "patient_touch" },
    triage: { priority: "urgent", rules_triggered: ["CHEST_PAIN_PLUS_DYSPNEA"], alerts: [] },
    documents: [],
    timeline: [{ at: "2026-09-08T00:00:00Z", kind: "answer", label: "Chief complaint", detail: "Chest pain" }],
    missing_information: ["No prior documents uploaded for review"],
    provenance: { patient_reported: ["cc_001"], document_extracted: [], physician_confirmed: [] },
  },
  summary: {
    patient_encounter: "Token A-900 · age 52 · language en · consent granted",
    chief_complaint: "Chest pain — onset 1–3 days ago",
    history_of_present_illness: "Severity: Severe [patient_touch]",
    past_medical_history: "None recorded",
    past_surgical_history: "None recorded",
    medications: "Not recorded",
    allergies: "None recorded",
    family_history: "None recorded",
    personal_social_history: "None recorded",
    review_of_systems: "None recorded",
    ayush_history: "Not collected",
    prior_investigations: "None uploaded",
    timeline: "",
    triage_status: "URGENT — red-flag rules: CHEST_PAIN_PLUS_DYSPNEA",
    missing_uncertain_information: "No prior documents uploaded for review",
  },
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function fakeBackend() {
  const calls: string[] = [];

  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input).replace(/^https?:\/\/[^/]+/, "");
    calls.push(path);

    if (
      path.startsWith(`/api/cases/by-session/${SESSION_ID}`) &&
      !path.includes("summary")
    ) {
      return json(CASE);
    }
    if (path.startsWith(`/api/cases/${CASE_ID}/summary`)) {
      return json({
        case_id: CASE_ID,
        session_id: SESSION_ID,
        status: "physician_edited",
        draft_version: 2,
        confirmed_at: null,
        message: "Summary draft saved.",
      });
    }
    if (path === `/api/cases/${CASE_ID}/confirm`) {
      return json({
        case_id: CASE_ID,
        session_id: SESSION_ID,
        status: "confirmed",
        draft_version: 3,
        confirmed_at: "2026-09-08T01:00:00Z",
        message: "Case confirmed as the clinical record.",
      });
    }
    return json({ status: "ok", service: "medikiosk-backend" });
  });

  return calls;
}

function renderCase() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const router = createMemoryRouter(routes, {
    initialEntries: [`/doctor/case/${SESSION_ID}`],
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

describe("physician case review", () => {
  it("renders the AI draft, urgent banner and editable sections", async () => {
    renderCase();

    expect(await screen.findByText("A-900")).toBeInTheDocument();
    expect(screen.getByText(/URGENT — red-flag rules triggered/i)).toBeInTheDocument();
    expect(screen.getByText(/Chest pain — onset 1–3 days ago/i)).toBeInTheDocument();
    // Appears both in the editable summary section and the missing-info card.
    expect(screen.getAllByText(/No prior documents uploaded for review/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Save draft/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Confirm clinical record/i })).toBeInTheDocument();
    // Export is gated on confirmation (ADR-007/018) — disabled while draft.
    expect(screen.getByRole("button", { name: /Export FHIR/i })).toBeDisabled();
  });

  it("saves physician edits via PATCH", async () => {
    const calls = fakeBackend();
    renderCase();

    const textarea = await screen.findByLabelText(/Chief Complaint/i);
    fireEvent.change(textarea, { target: { value: "Chest pain (edited)" } });
    fireEvent.click(screen.getByRole("button", { name: /Save draft/i }));

    expect(await screen.findByText("Draft saved.")).toBeInTheDocument();
    expect(calls.some((c) => c.includes("/summary"))).toBe(true);
  });

  it("confirms the record after the two-step confirmation", async () => {
    const calls = fakeBackend();
    renderCase();

    const confirmButton = await screen.findByRole("button", {
      name: /Confirm clinical record/i,
    });
    fireEvent.click(confirmButton);
    // Second click on the armed button performs the POST.
    const armed = await screen.findByRole("button", { name: /Confirm\? This locks/i });
    fireEvent.click(armed);

    expect(await screen.findByText("Clinical record confirmed.")).toBeInTheDocument();
    expect(calls.some((c) => c.endsWith("/confirm"))).toBe(true);
  });

  it("exports the confirmed case as a FHIR R4 Bundle", async () => {
    const calls: string[] = [];
    let confirmedState = false;
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input).replace(/^https?:\/\/[^/]+/, "");
      calls.push(`${init?.method ?? "GET"} ${path}`);

      if (
        path.startsWith(`/api/cases/by-session/${SESSION_ID}`) &&
        !path.includes("summary")
      ) {
        return json({
          ...CASE,
          status: confirmedState ? "confirmed" : "draft",
          confirmed_at: confirmedState ? "2026-09-08T01:00:00Z" : null,
        });
      }
      if (path === `/api/cases/${CASE_ID}/confirm`) {
        confirmedState = true;
        return json({
          case_id: CASE_ID,
          session_id: SESSION_ID,
          status: "confirmed",
          draft_version: 3,
          confirmed_at: "2026-09-08T01:00:00Z",
          message: "Case confirmed as the clinical record.",
        });
      }
      if (path === `/api/fhir/export/${CASE_ID}`) {
        return json({
          export_id: "44444444-4444-4444-4444-444444444444",
          case_id: CASE_ID,
          session_id: SESSION_ID,
          status: "succeeded",
          destination: "local",
          error: null,
          attempted_at: "2026-09-08T01:05:00Z",
          succeeded_at: "2026-09-08T01:05:00Z",
          created_at: "2026-09-08T01:05:00Z",
          bundle: {
            resourceType: "Bundle",
            type: "collection",
            entry: [{}, {}, {}],
          },
          message: "FHIR R4 Bundle generated from the confirmed case.",
        });
      }
      return json({ status: "ok", service: "medikiosk-backend" });
    });

    renderCase();

    const confirmButton = await screen.findByRole("button", {
      name: /Confirm clinical record/i,
    });
    fireEvent.click(confirmButton);
    const armed = await screen.findByRole("button", { name: /Confirm\? This locks/i });
    fireEvent.click(armed);

    // Export unlocks once the case status flips to confirmed.
    const exportButton = screen.getByRole("button", { name: /Export FHIR/i });
    await waitFor(() => expect(exportButton).not.toBeDisabled());
    fireEvent.click(exportButton);

    expect(
      await screen.findByText(/FHIR R4 Bundle exported successfully.*3 resources/i),
    ).toBeInTheDocument();
    expect(calls).toContain(`POST /api/fhir/export/${CASE_ID}`);
  });
});