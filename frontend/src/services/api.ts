/**
 * Centralized backend API client.
 *
 * The base URL comes from VITE_API_BASE_URL (see .env.example). Components and
 * stores must go through this module — never hard-code API URLs in the UI.
 */
import type {
  AnswerPayload,
  ApiErrorDetail,
  CaseActionResponse,
  CaseListResponse,
  CaseRead,
  Consent,
  ConsentPayload,
  DocumentReprocessResponse,
  FhirExportResponse,
  FhirExportStatusResponse,
  HealthResponse,
  InterviewAnswerResponse,
  InterviewNextResponse,
  Session,
  SessionCreate,
  SessionListResponse,
  SummaryPatch,
  TriageAckResponse,
  TriageActiveResponse,
} from "../types";

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: ApiErrorDetail | null;

  constructor(status: number, detail: ApiErrorDetail | null, message?: string) {
    super(message ?? detail?.message ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(0, null, `Cannot reach backend at ${API_BASE_URL}`);
  }

  if (!response.ok) {
    let detail: ApiErrorDetail | null = null;
    try {
      const body = (await response.json()) as { detail?: ApiErrorDetail };
      detail = body.detail ?? null;
    } catch {
      detail = null;
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

/** Readiness probe used by the app shell and health checks. */
export async function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

/** GET helper for typed resources. */
export async function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

/** POST helper for typed resources. */
export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

/** PATCH helper for typed resources. */
export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "PATCH",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

// --- Phase 2 / 2b endpoint helpers -----------------------------------------

/** POST /api/sessions — start a visit (patient is find-or-created). */
export async function createSession(
  payload: SessionCreate,
): Promise<Session> {
  return apiPost<Session>("/api/sessions", payload);
}

/** GET /api/sessions — physician queue listing. */
export async function listSessions(): Promise<SessionListResponse> {
  return apiGet<SessionListResponse>("/api/sessions");
}

/** POST /api/sessions/{id}/consent — record the consent decision. */
export async function recordConsent(
  sessionId: string,
  payload: ConsentPayload,
): Promise<Consent> {
  return apiPost<Consent>(`/api/sessions/${sessionId}/consent`, payload);
}

/** GET /api/triage/active — active red-flag alerts. */
export async function fetchActiveAlerts(): Promise<TriageActiveResponse> {
  return apiGet<TriageActiveResponse>("/api/triage/active");
}

/** POST /api/triage/{alert_id}/acknowledge — mark an alert as seen. */
export async function acknowledgeAlert(
  alertId: string,
): Promise<TriageAckResponse> {
  return apiPost<TriageAckResponse>(`/api/triage/${alertId}/acknowledge`);
}

/** GET /api/interview/{id}/next — next approved question. */
export async function fetchNextQuestion(
  sessionId: string,
): Promise<InterviewNextResponse> {
  return apiGet<InterviewNextResponse>(
    `/api/interview/${sessionId}/next`,
  );
}

/** POST /api/interview/{id}/answer — submit an answer. */
export async function submitAnswer(
  sessionId: string,
  payload: AnswerPayload,
): Promise<InterviewAnswerResponse> {
  return apiPost<InterviewAnswerResponse>(
    `/api/interview/${sessionId}/answer`,
    payload,
  );
}

// --- Phase 6: unified case + physician review -------------------------------

/** GET /api/cases — physician case list. */
export async function listCases(): Promise<CaseListResponse> {
  return apiGet<CaseListResponse>("/api/cases");
}

/** GET /api/cases/by-session/{id} — get-or-create the case for a session. */
export async function fetchCaseBySession(
  sessionId: string,
): Promise<CaseRead> {
  return apiGet<CaseRead>(`/api/cases/by-session/${sessionId}`);
}

/** GET /api/cases/{id} — full case by case id. */
export async function fetchCase(caseId: string): Promise<CaseRead> {
  return apiGet<CaseRead>(`/api/cases/${caseId}`);
}

/** PATCH /api/cases/{id}/summary — save physician edits. */
export async function patchCaseSummary(
  caseId: string,
  payload: SummaryPatch,
): Promise<CaseActionResponse> {
  return apiPatch<CaseActionResponse>(`/api/cases/${caseId}/summary`, payload);
}

/** POST /api/cases/{id}/confirm — confirm the clinical record. */
export async function confirmCase(caseId: string): Promise<CaseActionResponse> {
  return apiPost<CaseActionResponse>(`/api/cases/${caseId}/confirm`);
}

// --- Phase 4/2: document OCR/extraction --------------------------------------

/** POST /api/documents/{id}/reprocess — run OCR + clinical extraction now. */
export async function reprocessDocument(
  documentId: string,
): Promise<DocumentReprocessResponse> {
  return apiPost<DocumentReprocessResponse>(
    `/api/documents/${documentId}/reprocess`,
  );
}

// --- Phase 7: FHIR export (confirmed cases only) ------------------------------

/** POST /api/fhir/export/{caseId} — export a confirmed case as a FHIR R4 Bundle. */
export async function exportFhir(caseId: string): Promise<FhirExportResponse> {
  return apiPost<FhirExportResponse>(`/api/fhir/export/${caseId}`);
}

/** GET /api/fhir/export/{caseId} — last export attempt for the case. */
export async function fetchFhirExport(
  caseId: string,
): Promise<FhirExportStatusResponse> {
  return apiGet<FhirExportStatusResponse>(`/api/fhir/export/${caseId}`);
}
