/**
 * Transport types for the MediKiosk backend.
 *
 * These mirror the API contract (docs/API_CONTRACT.md) and the canonical
 * internal model (docs/DATA_MODEL.md). The backend Pydantic schemas are the
 * authoritative definitions; keep this file in sync with them.
 */

// --- Enumerations ----------------------------------------------------------

export type SessionState =
  | "welcome"
  | "identity"
  | "consent"
  | "chief_complaint"
  | "hpi"
  | "past_history"
  | "medications"
  | "allergies"
  | "family_history"
  | "personal_history"
  | "ros"
  | "ayush"
  | "documents"
  | "summary_review"
  | "submitted"
  | "closed";

export type InputMode = "voice" | "touch" | "manual" | (string & {});

export type DocumentType =
  | "prescription"
  | "lab_report"
  | "discharge_summary"
  | "imaging_report"
  | "other"
  | "unknown"
  | (string & {});

export type DocumentProcessingStatus = "uploaded" | "processing" | "completed" | "failed";

export type TriagePriority = "routine" | "urgent";
export type TriageAlertStatus = "active" | "acknowledged" | (string & {});

export type CaseStatus = "draft" | "physician_edited" | "confirmed" | (string & {});

export type UserRole = "doctor" | "triage" | "admin";

// --- Core resources --------------------------------------------------------

export interface Patient {
  id: string; // UUID
  external_token?: string | null;
  name?: string | null;
  age?: number | null;
  sex?: string | null;
  preferred_language?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface SessionListItem {
  session_id: string;
  token?: string | null;
  patient_name?: string | null;
  age?: number | null;
  language?: string | null;
  department?: string | null;
  state: string;
  consent_granted?: boolean | null; // null = decision not recorded yet
  chief_complaint?: string | null;
  is_demo?: boolean;
  started_at: string;
  completed_at?: string | null;
}

export interface SessionListResponse {
  count: number;
  items: SessionListItem[];
}

export interface Session {
  session_id: string; // UUID (wire identifier; backend column is `id`)
  patient_id?: string | null;
  case_id?: string | null; // null until the summary milestone creates a case
  state: SessionState | (string & {});
  mode?: InputMode | null;
  department?: string | null;
  started_at: string;
  completed_at?: string | null;
  is_demo?: boolean;
}

export interface Consent {
  id: string;
  session_id: string;
  granted: boolean;
  purposes?: string[] | null;
  consent_text_version?: string | null;
  created_at: string;
  revoked_at?: string | null;
}

export interface Answer {
  id: string;
  session_id: string;
  question_id: string;
  input_mode?: InputMode | null;
  raw_answer?: string | null;
  structured_value?: Record<string, unknown> | null;
  confidence?: number | null;
  source?: string | null;
  created_at: string;
}

export interface Document {
  id: string;
  session_id: string;
  file_name: string;
  mime_type?: string | null;
  sha256?: string | null;
  document_type?: DocumentType | null;
  storage_path?: string | null;
  processing_status: DocumentProcessingStatus | (string & {});
  uploaded_at: string;
  // --- Phase 4/2: OCR/extraction results (null until processed) ---
  extraction?: DocumentExtraction | null;
  page_count?: number | null;
  ocr_provider?: string | null;
  ocr_mocked?: boolean | null;
  processed_at?: string | null;
  last_error?: string | null;
}

/** One extracted lab test row (provenance = document_extracted). */
export interface ExtractedTest {
  name: string;
  value: number;
  unit: string;
  reference_low?: number | null;
  reference_high?: number | null;
  status: "high" | "low" | "normal" | "unknown" | (string & {});
  source_text?: string;
}

/** Structured OCR/extraction payload persisted on a completed document. */
export interface DocumentExtraction {
  provider: string;
  mocked: boolean;
  confidence?: number | null;
  page_count: number;
  pages?: Array<{
    page_number: number;
    lines?: Array<{ text: string; confidence?: number | null; box?: unknown }>;
  }>;
  text: string;
  document_type?: string | null;
  document_type_label?: string | null;
  classification_method?: string;
  tests: ExtractedTest[];
  abnormal_values: ExtractedTest[];
  medications: Array<{ name: string; raw_text?: string; strength?: string | null; source_text?: string }>;
  conditions: Array<{ text: string; source_text?: string }>;
  engine_note: string;
}

/** POST /documents/{id}/reprocess response (Phase 4/2). */
export interface DocumentReprocessResponse {
  document_id: string;
  session_id: string;
  status: DocumentProcessingStatus | (string & {});
  document_type?: string | null;
  page_count?: number | null;
  ocr_provider?: string | null;
  ocr_mocked?: boolean | null;
  confidence?: number | null;
  extraction?: DocumentExtraction | null;
  processed_at?: string | null;
  error?: string | null;
  message: string;
}

export interface TriageAlert {
  id: string;
  session_id: string;
  priority: TriagePriority | (string & {});
  rules_triggered?: string[] | null;
  message?: string | null;
  status: TriageAlertStatus;
  created_at: string;
  acknowledged_at?: string | null;
}

export interface CaseSummary {
  id: string;
  session_id: string;
  status: CaseStatus;
  content?: Record<string, unknown> | null;
  draft_version: number;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  updated_at: string;
}

export interface CaseVersion {
  id: string;
  case_summary_id: string;
  version_number: number;
  status: CaseStatus;
  content: Record<string, unknown>;
  edited_by?: string | null;
  created_at: string;
}

// --- Interview (Phase 2b: deterministic touch interview) ---------------------

export interface InterviewChoice {
  code: string;
  label_en: string;
  label_hi?: string | null;
}

export interface InterviewQuestion {
  question_id: string;
  section: string;
  prompt_en: string;
  prompt_hi?: string | null;
  input: "choice" | "multi" | "text" | (string & {});
  required: boolean;
  allow_other: boolean;
  choices: InterviewChoice[];
}

export interface InterviewNextResponse {
  state: string;
  completed: boolean;
  question: InterviewQuestion | null;
}

export interface AnswerPayload {
  question_id: string;
  input_mode?: "touch" | "voice" | "manual" | (string & {});
  choice_codes?: string[] | null;
  text?: string | null;
}

export interface InterviewAnswerResponse {
  saved: boolean;
  state: string;
  completed: boolean;
  question: InterviewQuestion | null;
  triage?: null;
}

// --- Triage (Phase 3b: deterministic red-flag alerts) ------------------------

export interface TriageAlertRow {
  alert_id: string;
  session_id: string;
  priority: string;
  status: string;
  message?: string | null;
  rules_triggered: string[];
  token?: string | null;
  chief_complaint?: string | null;
  created_at: string;
}

export interface TriageActiveResponse {
  count: number;
  items: TriageAlertRow[];
}

export interface TriageAckResponse {
  alert_id: string;
  status: string;
}

export interface ConsentPayload {
  granted: boolean;
  purposes?: string[] | null;
  consent_text_version?: string | null;
}

// --- Case (Phase 6: unified case + physician review) -------------------------

/** Canonical case sections the UI reads directly (see docs/DATA_MODEL.md §1). */
export interface CaseCanonical {
  case_id?: string | null;
  session_id?: string;
  status?: string;
  draft_version?: number;
  patient?: {
    patient_id?: string | null;
    token?: string | null;
    name?: string | null;
    age?: number | null;
    sex?: string | null;
    preferred_language?: string | null;
  } | null;
  consent?: { granted?: boolean; purposes?: string[]; timestamp?: string } | null;
  chief_complaint?: {
    code?: string | null;
    text?: string | null;
    onset?: string | null;
    source?: string | null;
    confidence?: number | null;
  } | null;
  hpi?: Record<string, unknown>;
  past_history?: Array<{ text: string; source?: string | null; question_id?: string | null }>;
  surgical_history?: { text?: string; source?: string | null } | null;
  medications?: { taking?: string | null; list?: Array<{ text: string; source?: string | null }> };
  allergies?: Array<{ text: string; source?: string | null }>;
  family_history?: Array<{ text: string; source?: string | null }>;
  personal_history?: Record<string, unknown>;
  review_of_systems?: Array<{ text: string; source?: string | null }>;
  ayush?: unknown;
  documents?: Array<{
    document_id?: string;
    file_name?: string;
    document_type?: string | null;
    processing_status?: string;
    uploaded_at?: string;
    source?: string;
    ocr_provider?: string | null;
    ocr_mocked?: boolean | null;
    page_count?: number | null;
    processed_at?: string | null;
    abnormal_values?: Array<{
      name: string;
      value: number;
      unit: string;
      status: string;
    }>;
    tests?: Array<{ name: string; value: number; unit: string; status: string }>;
    medications?: Array<{ name: string; raw_text?: string; strength?: string | null }>;
    conditions?: Array<{ text: string; source_text?: string }>;
  }>;
  investigations?: unknown[];
  timeline?: Array<{ at?: string; kind?: string; label?: string; detail?: string }>;
  triage?: {
    priority?: string;
    rules_triggered?: string[];
    alerts?: Array<{ alert_id?: string; rule_id?: string; message?: string | null; status?: string }>;
  };
  missing_information?: string[];
  provenance?: {
    patient_reported?: string[];
    document_extracted?: string[];
    physician_confirmed?: string[];
  };
}

export interface CaseRead {
  case_id: string;
  session_id: string;
  status: CaseStatus | (string & {});
  draft_version: number;
  canonical: CaseCanonical;
  summary: Record<string, string>;
  updated_at: string;
  confirmed_at?: string | null;
}

export interface CaseListItem {
  session_id: string;
  case_id?: string | null;
  token?: string | null;
  patient_name?: string | null;
  age?: number | null;
  language?: string | null;
  department?: string | null;
  state: string;
  consent_granted?: boolean | null;
  chief_complaint?: string | null;
  status?: CaseStatus | string | null;
  has_documents?: boolean;
  urgent_alerts?: number;
  started_at: string;
  completed_at?: string | null;
  confirmed_at?: string | null;
}

export interface CaseListResponse {
  count: number;
  items: CaseListItem[];
}

export interface SummaryPatch {
  summary: Record<string, string>;
  note?: string | null;
}

export interface CaseActionResponse {
  case_id: string;
  session_id: string;
  status: string;
  draft_version: number;
  confirmed_at?: string | null;
  message: string;
}

// --- FHIR export (Phase 7: confirmed case → FHIR R4 Bundle) ------------------

export interface FhirExportResponse {
  export_id: string;
  case_id: string;
  session_id: string;
  status: "pending" | "succeeded" | "failed" | (string & {});
  destination?: string | null;
  error?: string | null;
  attempted_at?: string | null;
  succeeded_at?: string | null;
  created_at: string;
  bundle?: Record<string, unknown> | null;
  message: string;
}

export interface FhirExportStatusResponse {
  case_id: string;
  session_id: string;
  export?: FhirExportResponse | null; // null = never exported
}

// --- Requests / misc --------------------------------------------------------

export interface SessionCreate {
  token?: string | null;
  language?: string;
  department?: string | null;
  demo?: boolean;
}

export interface HealthResponse {
  status: string;
  service: string;
  environment?: string | null;
  database?: string | null;
  version?: string | null;
  demo_mode?: boolean | null;
}

export interface ApiErrorDetail {
  status: string;
  code?: string;
  message?: string;
  feature?: string;
  phase?: number;
}
