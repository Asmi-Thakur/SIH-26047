/**
 * Phase 4/2: documents screen over the mocked HTTP API.
 * Upload -> reprocess (OCR) -> extraction result with honest mock labelling.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentsPage } from "./DocumentsPage";
import { IntakeProvider, useIntake } from "../../state/sessionStore";

const SESSION_ID = "22222222-2222-2222-2222-222222222222";

const UPLOADED = {
  document_id: "33333333-3333-3333-3333-333333333333",
  session_id: SESSION_ID,
  file_name: "lab.png",
  mime_type: "image/png",
  sha256: "abc",
  document_type: null,
  processing_status: "uploaded",
  uploaded_at: "2026-09-08T00:00:00Z",
  extraction: null,
};

const PROCESSED = {
  document_id: UPLOADED.document_id,
  session_id: SESSION_ID,
  status: "completed",
  document_type: "lab_report",
  page_count: 1,
  ocr_provider: "mock",
  ocr_mocked: true,
  confidence: 0.99,
  extraction: {
    provider: "mock",
    mocked: true,
    confidence: 0.99,
    page_count: 1,
    pages: [],
    text: "Demo Diagnostics Laboratory\nGlucose 145 mg/dL (Ref 70-140) HIGH",
    document_type: "lab_report",
    document_type_label: "Lab report",
    classification_method: "keyword_v1",
    tests: [
      {
        name: "Glucose",
        value: 145,
        unit: "mg/dL",
        reference_low: 70,
        reference_high: 140,
        status: "high",
        source_text: "Glucose 145 mg/dL (Ref 70-140) HIGH",
      },
    ],
    abnormal_values: [
      {
        name: "Glucose",
        value: 145,
        unit: "mg/dL",
        reference_low: 70,
        reference_high: 140,
        status: "high",
        source_text: "Glucose 145 mg/dL (Ref 70-140) HIGH",
      },
    ],
    medications: [],
    conditions: [],
    engine_note: "Deterministic mock fixture — NOT real OCR of the uploaded file.",
  },
  processed_at: "2026-09-08T00:01:00Z",
  error: null,
  message: "OCR + extraction completed (mock provider — simulated text, not real OCR).",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function fakeBackend() {
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const path = url.replace(/^https?:\/\/[^/]+/, "");

    if (path === "/api/documents/upload") {
      return json(UPLOADED, 201);
    }
    if (path.endsWith("/reprocess")) {
      return json(PROCESSED);
    }
    return json({ status: "ok", service: "medikiosk-backend" });
  });
}

/** Starts a kiosk session then renders the documents screen. */
function Harness() {
  const { startSession } = useIntake();
  useEffect(() => {
    startSession(SESSION_ID);
  }, [startSession]);
  return <DocumentsPage />;
}

function renderDocuments() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <IntakeProvider>
        <Harness />
      </IntakeProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fakeBackend();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("documents screen (Phase 4/2)", () => {
  it("shows upload options and skip", () => {
    renderDocuments();

    expect(
      screen.getByRole("button", { name: /Upload image/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Upload PDF/i }),
    ).toBeInTheDocument();
  });

  it("uploads, processes, and labels simulated OCR honestly", async () => {
    renderDocuments();

    const input = document.querySelector(
      'input[type="file"][accept^="image/"]',
    ) as HTMLInputElement;
    expect(input).not.toBeNull();

    const file = new File(["png"], "lab.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });

    // The result card renders with the flagged abnormal value…
    expect(
      await screen.findByText(/Glucose 145 mg\/dL/i, {}, { timeout: 2500 }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Values outside the reference range/i),
    ).toBeInTheDocument();

    // …and the simulated-OCR badge is honest about it.
    expect(screen.getByText("Simulated OCR")).toBeInTheDocument();
    expect(
      screen.getByText(/NOT real OCR of the uploaded file/i),
    ).toBeInTheDocument();
  });
});
