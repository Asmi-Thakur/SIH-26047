# MediKiosk — API Contract

> Base URL: `http://localhost:8000/api` (local) — all paths below are relative to `/api`.
> Source of truth for product behaviour: `docs/PROTOTYPE_BUILD_SPEC.md` §25.
> Implemented to date: health (1), sessions (2), interview (2b), triage (3b),
> speech (3c), LLM extraction (3d), document upload/status (4), **document
> OCR/reprocess (4/2)**, cases (6), FHIR export (7), AYUSH section (8).
> Remaining 501s: **none**.
> Contract changes must be mirrored in `backend/app/schemas/*`,
> `frontend/src/types/index.ts` and this document.

## Conventions

- JSON request/response bodies unless stated (multipart for uploads/audio).
- Errors use the shape:

```json
{
  "detail": {
    "status": "error",
    "code": "string",
    "message": "human readable message"
  }
}
```

- Deferred endpoints return:

```json
{
  "detail": {
    "status": "not_implemented",
    "feature": "sessions.create",
    "phase": 2,
    "message": "Planned for Phase 2 — see docs/API_CONTRACT.md"
  }
}
```

- Timestamps are ISO 8601 with timezone (UTC).

## Status legend

| Mark | Meaning |
|---|---|
| ✅ | Implemented |
| 🚧 | Planned — 501 placeholder endpoint exists |
| ⏳ | Planned later — endpoint not yet mounted |

---

## Health

| Method | Path | Status | Description |
|---|---|---|---|
| GET | `/health` (root, not under `/api`) | ✅ | Liveness: `{"status":"ok","service":"medikiosk-backend"}` |
| GET | `/api/health` | ✅ | Readiness incl. DB ping: adds `database: "ok" \| "unavailable"` |
| GET | `/` (root) | ✅ | Service metadata (name, version, docs URL, demo mode) |

---

## Sessions

| Method | Path | Status | Description |
|---|---|---|---|
| GET | `/sessions` | ✅ | Physician queue: sessions joined with patient/consent/chief complaint, active first |
| POST | `/sessions` | ✅ | Create patient session (starts at `state: identity`) |
| GET | `/sessions/{session_id}` | ✅ | Current session state |
| POST | `/sessions/{session_id}/consent` | ✅ | Store/revise consent decision (single row per session) |

`POST /sessions` request:

```json
{ "token": "A-104", "language": "hi", "department": "ayush", "demo": true }
```

`POST /sessions` / `GET /sessions/{session_id}` response:

```json
{
  "session_id": "4aedebf2-...",
  "patient_id": "d58d4bd8-...",
  "case_id": null,
  "state": "identity",
  "mode": null,
  "department": "ayush",
  "is_demo": false,
  "started_at": "2026-09-07T14:06:20.542466",
  "completed_at": null
}
```

`GET /sessions` response (list item inside `{count, items}`):

```json
{
  "session_id": "4aedebf2-...",
  "token": "A-104",
  "patient_name": null,
  "age": null,
  "language": "en",
  "department": "ayush",
  "state": "hpi",
  "consent_granted": true,
  "chief_complaint": "Chest pain",
  "is_demo": true,
  "started_at": "2026-09-07T14:06:20.542466",
  "completed_at": null
}
```

(`consent_granted` is null until decided; `chief_complaint` is null until the
chief-complaint question is answered; active sessions sort before completed.)

Behaviour notes:

- No `token` → a walk-in patient row is created; `token` present → patient is
  find-or-created by `external_token`. `language` is stored on the patient.
- Consent upserts one `consents` row per session (revisits update it) and
  writes `CONSENT_GRANTED` / `CONSENT_DECLINED` audit events.
- Unknown `session_id` → 404 with `code: "session_not_found"`.
- Consent on its own does not advance the state machine; the interview module
  (Phase 2b) moves a session past `identity`.

---

## Interview

| Method | Path | Status | Description |
|---|---|---|---|
| GET | `/interview/{session_id}/next` | ✅ | Next approved question from the state machine |
| POST | `/interview/{session_id}/answer` | ✅ | Submit an answer (touch choice or text) |

Behaviour notes:

- Requires a recorded consent decision (granted or declined) → else **409
  `consent_required`**.
- Progress is deterministic and derived from recorded answers (per spec §8
  section order); questions gated by chief complaint (`for_complaints`) are
  skipped for unrelated complaints (SOCRATES-style conditional HPI, §11–12).
- Only the expected next question may be answered → else **409
  `question_not_current`**. Unknown choice codes → **422**.
- **AYUSH gating (spec §14, Phase 8):** sessions created with
  `department: "ayush"` receive the Dashavidha Pariksha / Ahara-Vihara
  section (`ay_*` questions) after ROS; all other sessions never see those
  questions. Content lives in the question bank (`department_for:
  ["ayush"]`) — structured capture only, never a diagnosis.
- When every section is complete the response is `completed: true` with
  `state: "documents"` and `question: null`.
- `triage` is always `null` until the deterministic rule engine lands.

`GET /interview/{session_id}/next` response:

```json
{
  "state": "chief_complaint",
  "completed": false,
  "question": {
    "question_id": "cc_001",
    "section": "chief_complaint",
    "prompt_en": "What brought you to the hospital today?",
    "prompt_hi": "आज आप अस्पताल क्यों आए हैं?",
    "input": "choice",
    "required": true,
    "allow_other": true,
    "choices": [
      { "code": "chest_pain", "label_en": "Chest pain", "label_hi": "सीने में दर्द" }
    ]
  }
}
```

`POST /interview/{session_id}/answer` request:

```json
{ "question_id": "cc_001", "input_mode": "touch", "choice_codes": ["chest_pain"] }
```

`POST /interview/{session_id}/answer` response (same envelope as /next with
`"saved": true`; `question` is the follow-up):

```json
{
  "saved": true,
  "state": "hpi",
  "completed": false,
  "question": { "question_id": "hpi_001", "section": "hpi", "prompt_en": "When did your problem start?", "prompt_hi": "यह समस्या कब शुरू हुई?", "input": "choice", "required": true, "allow_other": false, "choices": [] },
  "triage": null
}
```

Question content: `backend/app/clinical/questions/bank/questions.json`
(versioned, validated by Pydantic on load — edit content there, never in the
router).

---

## Speech

| Method | Path | Status | Description |
|---|---|---|---|
| POST | `/speech/transcribe` | ✅ | Multipart audio + language → transcript (mock provider; real ASR next) |
| POST | `/speech/synthesize` | ✅ | Text + language → audio/wav bytes (mock TTS) |

Behaviour notes:

- Provider selected by `SPEECH_PROVIDER` (default `mock`). Only the mock is
  implemented; responses include `provider` and `mocked: true` so the UI can
  label simulated transcription honestly. Setting `SPEECH_PROVIDER` to a real
  vendor raises until that vendor's provider exists (see docs/AI_HANDOFF.md).
- The mock transcribe ignores the uploaded bytes and returns a deterministic
  bilingual sample (en/hi); mock synthesize returns a short silent WAV.

`POST /speech/transcribe` (multipart): `language` (form) + `audio` (file)

`POST /speech/transcribe` response:

```json
{
  "transcript": "I have had chest pain for three days and I also feel short of breath.",
  "language": "en",
  "provider": "mock",
  "mocked": true
}
```

`POST /speech/synthesize` request:

```json
{ "text": "कृपया दर्द के बारे में बताइए", "language": "hi" }
```

---

## LLM extraction

| Method | Path | Status | Description |
|---|---|---|---|
| POST | `/llm/extract` | ✅ | Free-text narration → structured fields + missing information (mock default; Gemini when configured) |

Behaviour notes:

- `LLM_PROVIDER=mock` (default) runs a deterministic keyword extractor and
  reports `mocked: true`. With `LLM_PROVIDER=gemini` and `GEMINI_API_KEY`
  set, a REST call returns strict JSON against the same contract; malformed
  or failed responses fall back to the deterministic extractor (still
  labelled `mocked: true`). Output is extraction, never a diagnosis.

`POST /llm/extract` request:

```json
{ "text": "I have diabetes and take metformin. Feeling dizzy since yesterday.", "language": "en" }
```

Response `fields`: `complaint[]`, `duration|null`, `conditions[]`,
`medications[]`, `missing_information[]`.

---

## Documents

| Method | Path | Status | Description |
|---|---|---|---|
| POST | `/documents/upload` | ✅ | Validated multipart upload (jpg/jpeg/png/webp/pdf); original retained |
| GET | `/documents/{document_id}` | ✅ | Metadata + processing status + structured extraction |
| POST | `/documents/{document_id}/reprocess` | ✅ | Run OCR + clinical extraction on the retained original (Phase 4/2) |

Behaviour notes:

- Multipart form: `session_id` + `file`. Invalid MIME/extension → 415
  `unsupported_media_type`; over `MAX_UPLOAD_MB` → 413 `payload_too_large`;
  unknown session → 404 `session_not_found`.
- The original file is retained under `UPLOAD_DIR` (default
  `storage/uploads`) so every later extraction is traceable to its source.
- **Reprocess lifecycle (Phase 4/2):** `uploaded | completed | failed →
  processing → completed | failed` (409 `document_already_processing` while
  mid-flight). Requires a **granted** consent row → else 409
  `consent_required` (declined consent blocks document processing, spec
  P03). Unknown document → 404 `document_not_found`.
- **Providers (ADR-020):** `OCR_PROVIDER=auto` (default) runs **real
  PaddleOCR** when the paddle packages are importable (py3.10–3.12 venv,
  `requirements-ocr.txt`), otherwise falls back to the deterministic mock
  which is **labelled `mocked: true` everywhere it appears**. `mock` forces
  simulation; `paddleocr` forces the real engine and **raises** if it is not
  installed (never silently degrades).
- Classification (spec §16.3) is keyword-based over the OCR text;
  clinical extraction is deterministic: lab tests with value/unit/
  reference-range/`status` (ranges come only from the document — no range →
  `unknown`, never invented, spec §21), medication lines and condition
  mentions. Everything carries `source_text` and `document_extracted`
  provenance. A failed OCR run marks the document `failed` with a persisted
  `last_error` (retryable) and returns a readable response — never a bare 5xx.

`POST /documents/upload` response:

```json
{
  "document_id": "4aedebf2-...",
  "session_id": "4aedebf2-...",
  "file_name": "lab.png",
  "mime_type": "image/png",
  "sha256": "…",
  "document_type": null,
  "processing_status": "uploaded",
  "uploaded_at": "2026-09-07T14:06:20.542466",
  "extraction": null,
  "page_count": null,
  "ocr_provider": null,
  "ocr_mocked": null,
  "processed_at": null,
  "last_error": null
}
```

`POST /documents/{document_id}/reprocess` response
(`DocumentReprocessResponse`; a failed run returns the same shape with
`status: "failed"`, `error` populated and `extraction: null`):

```json
{
  "document_id": "4aedebf2-...",
  "session_id": "4aedebf2-...",
  "status": "completed",
  "document_type": "lab_report",
  "page_count": 1,
  "ocr_provider": "paddleocr",
  "ocr_mocked": false,
  "confidence": 0.9955,
  "extraction": {
    "provider": "paddleocr",
    "mocked": false,
    "confidence": 0.9955,
    "page_count": 1,
    "pages": [{ "page_number": 1, "lines": [{ "text": "Glucose 145 mg/dL (Ref 70-140) HIGH", "confidence": 0.99, "box": null }] }],
    "text": "Demo Diagnostics Laboratory\nGlucose 145 mg/dL (Ref 70-140) HIGH",
    "document_type": "lab_report",
    "document_type_label": "Lab report",
    "classification_method": "keyword_v1",
    "tests": [{ "name": "Glucose", "value": 145, "unit": "mg/dL", "reference_low": 70, "reference_high": 140, "status": "high", "source_text": "Glucose 145 mg/dL (Ref 70-140) HIGH" }],
    "abnormal_values": [{ "name": "Glucose", "value": 145, "unit": "mg/dL", "status": "high" }],
    "medications": [],
    "conditions": [],
    "engine_note": "Real PaddleOCR output of the retained original."
  },
  "processed_at": "2026-09-08T…",
  "error": null,
  "message": "OCR + extraction completed with the real PaddleOCR engine."
}
```

---

## Triage

| Method | Path | Status | Description |
|---|---|---|---|
| GET | `/triage/active` | ✅ | Active (urgent) red-flag alerts with token + chief complaint |
| POST | `/triage/{alert_id}/acknowledge` | ✅ | Mark alert acknowledged (clears the active queue) |

Behaviour notes:

- Alerts are created **deterministically** (spec §13) the moment an answer
  lands: rules live in `backend/app/clinical/rules/rules.json` and evaluate
  structured symptom buckets (`chief_complaint` ← cc_001, `associated` ←
  hpi_004, `severity` ← hpi_003). Current rules: `CHEST_PAIN_PLUS_DYSPNEA`,
  `STROKE_LIKE_SYMPTOMS`, `SEVERE_BREATHING_DIFFICULTY`.
- One alert per (session, rule) stays active until acknowledged; duplicate
  triggers are ignored while active. `RED_FLAG_CREATED` audit events are
  written.
- Unknown `alert_id` → 404 with `code: "alert_not_found"`.

`GET /triage/active` item:

```json
{
  "alert_id": "4aedebf2-...",
  "session_id": "4aedebf2-...",
  "priority": "urgent",
  "status": "active",
  "message": "Chest pain with breathing difficulty reported. Immediate human triage required.",
  "rules_triggered": ["CHEST_PAIN_PLUS_DYSPNEA"],
  "token": "A-104",
  "chief_complaint": "Chest pain",
  "created_at": "2026-09-07T14:06:20.542466"
}
```

---

## Cases

| Method | Path | Status | Description |
|---|---|---|---|
| GET | `/cases` | ✅ | Physician case list (every session + its case row) |
| GET | `/cases/by-session/{session_id}` | ✅ | Get-or-create the unified case for a session |
| GET | `/cases/{case_id}` | ✅ | Full case: canonical model + editable summary draft |
| PATCH | `/cases/{case_id}/summary` | ✅ | Save physician edits (409 once confirmed) |
| POST | `/cases/{case_id}/confirm` | ✅ | Lock the confirmed clinical record (gates FHIR) |

Behaviour notes:

- A “case” is the `case_summaries` row for a session; `case_id` = its UUID.
  It is created lazily on the first physician read (`by-session`) with a
  deterministic draft and an immutable `case_versions` v1 snapshot
  (`CASE_CREATED` audit). `GET /sessions/{id}` returns `case_id` once the row
  exists.
- The response carries **both** the machine-readable canonical case (freshly
  re-assembled from recorded answers — never cached stale) and the
  physician-ready summary draft (editable). Every canonical item keeps its
  `source` (`patient_touch` / `document_uploaded` / …) and the summary labels
  sources inline (`[patient_reported]`).
- `PATCH …/summary` merges the supplied text sections, bumps `draft_version`,
  writes a `physician_edited` version snapshot and a `CASE_EDITED` audit
  event. Editing a **confirmed** case → **409 `case_confirmed`** (immutable,
  ADR-007).
- `POST …/confirm` sets `confirmed` + `confirmed_at`, writes an immutable
  `confirmed` version and a `CASE_CONFIRMED` audit event. Confirming twice →
  **409 `case_confirmed`**. FHIR export (Phase 7) requires `confirmed`.
- **Document extraction in the case (Phase 4/2):** completed documents carry
  `ocr_provider`, `ocr_mocked`, `page_count`, `abnormal_values`, `tests`,
  `medications` and `conditions` in `canonical.documents`; completed
  `lab_report`/`imaging_report` rows also appear in
  `canonical.investigations`; abnormal values become `document_extracted`
  timeline events; `provenance.document_extracted` lists processed document
  ids. The summary's `prior_investigations` section repeats flagged values
  with `[document_extracted]` and labels simulated runs `[mocked OCR]`.
- **AYUSH block (Phase 8):** `canonical.ayush` is `null` until Dashavidha
  answers exist; when collected it is `{ collected: true, department:
  "ayush", items: [{ text, source, question_id, field }], disclaimer }` —
  structured practitioner-relevant history only, never a diagnosis
  (spec §14.3). The summary's `ayush_history` section renders the labelled
  items ("Not collected" when absent).
- Unknown `case_id` → 404 `case_not_found`; unknown session on `by-session` →
  404 `session_not_found`.

`GET /cases` item:

```json
{
  "session_id": "4aedebf2-...",
  "case_id": "9b2f…-…",
  "token": "A-900",
  "patient_name": null,
  "age": 52,
  "language": "en",
  "department": null,
  "state": "hpi",
  "consent_granted": true,
  "chief_complaint": "Chest pain",
  "status": "draft",
  "has_documents": false,
  "urgent_alerts": 1,
  "started_at": "2026-09-08T…",
  "completed_at": null,
  "confirmed_at": null
}
```

`GET /cases/{case_id}` (also `/cases/by-session/{session_id}`):

```json
{
  "case_id": "9b2f…-…",
  "session_id": "4aedebf2-...",
  "status": "draft",
  "draft_version": 1,
  "canonical": {
    "case_id": "…", "session_id": "…", "status": "draft", "draft_version": 1,
    "patient": { "token": "A-900", "age": 52, "preferred_language": "en" },
    "consent": { "granted": true, "purposes": [], "timestamp": "…" },
    "chief_complaint": { "code": "chest_pain", "text": "Chest pain", "onset": "1–3 days ago", "source": "patient_touch" },
    "hpi": { "severity": { "text": "Severe", "source": "patient_touch" }, "associated": [ { "text": "Breathing difficulty", "source": "patient_touch" } ] },
    "past_history": [ { "text": "Diabetes (sugar)", "source": "patient_touch" } ],
    "surgical_history": { "text": "No", "source": "patient_touch" },
    "medications": { "taking": "Yes, I take medicines", "list": [ { "text": "Metformin 500 mg twice a day", "source": "patient_touch" } ] },
    "allergies": [ { "text": "Penicillin", "source": "patient_touch" } ],
    "family_history": [], "personal_history": {}, "review_of_systems": [],
    "ayush": null,
    "documents": [],
    "investigations": [],
    "timeline": [ { "at": "…", "kind": "answer", "label": "Chief complaint", "detail": "Chest pain" } ],
    "triage": { "priority": "urgent", "rules_triggered": ["CHEST_PAIN_PLUS_DYSPNEA"], "alerts": [] },
    "missing_information": [ "No prior documents uploaded for review" ],
    "provenance": { "patient_reported": ["cc_001", …], "document_extracted": [], "physician_confirmed": [] }
  },
  "summary": {
    "patient_encounter": "Token A-900 · age 52 · language en · consent granted",
    "chief_complaint": "Chest pain — onset 1–3 days ago",
    "history_of_present_illness": "Severity: Severe [patient_touch] · …",
    "past_medical_history": "Diabetes (sugar) [patient_touch]",
    "past_surgical_history": "No [patient_touch]",
    "medications": "Taking medicines: Yes, I take medicines — Metformin 500 mg twice a day",
    "allergies": "Penicillin [patient_touch]",
    "family_history": "None recorded",
    "personal_social_history": "Never [patient_touch]; Occasionally [patient_touch]",
    "review_of_systems": "None reported [patient_touch]",
    "ayush_history": "Not collected",
    "prior_investigations": "None uploaded",
    "timeline": "…",
    "triage_status": "URGENT — red-flag rules: CHEST_PAIN_PLUS_DYSPNEA",
    "missing_uncertain_information": "No prior documents uploaded for review"
  },
  "updated_at": "2026-09-08T…",
  "confirmed_at": null
}
```

`PATCH /cases/{case_id}/summary` request:

```json
{ "summary": { "chief_complaint": "Chest pain (physician edited)" }, "note": "checked" }
```

`PATCH` / `POST …/confirm` response (`CaseActionResponse`):

```json
{ "case_id": "…", "session_id": "…", "status": "physician_edited", "draft_version": 2, "confirmed_at": null, "message": "Summary draft saved." }
```

---

## FHIR

| Method | Path | Status | Description |
|---|---|---|---|
| POST | `/fhir/export/{case_id}` | ✅ | Map **confirmed** case → FHIR R4 Bundle, persist the attempt |
| GET | `/fhir/export/{case_id}` | ✅ | Last export attempt for the case (`export: null` if never exported) |

Behaviour notes:

- **Gating (ADR-007/018):** the case must be `confirmed` → else **409
  `case_not_confirmed`**. Consent must have been **granted** for the session →
  else **409 `consent_required`**. Unknown case → 404 `case_not_found`.
- The bundle is built from the canonical case re-assembled from recorded
  facts (ADR-005) by `backend/app/services/fhir/mapper.py`. Resources carry a
  `source` extension (`http://medikiosk.example.org/fhir/StructureDefinition/source`)
  normalised to `patient_reported` / `document_extracted` /
  `physician_confirmed`, so provenance survives into FHIR.
- **Condition resources are created ONLY from `physician_confirmed` items** —
  patient-reported problems stay `Observation` (AI never produces a diagnosis,
  ADR-009). Allergies → `AllergyIntolerance`, medication lines →
  `MedicationStatement`, uploaded documents → `DocumentReference` (with a
  `processing-status` extension), and a `Composition` carries the
  source-labelled narrative sections. Bundle `type: collection` with
  deterministic `urn:uuid` ids (uuid5 of the case id).
- Every attempt is persisted to `fhir_exports` (`pending → succeeded|failed`);
  a mapper failure produces a `failed` row with `error` (never a 500) and can
  be retried. `FHIR_EXPORTED` / `FHIR_EXPORT_FAILED` audit events are written.
- `destination` is `local` for now — ABDM / live FHIR-server push remains a
  future `HealthRecordAdapter` boundary (ADR-011); **no live ABDM integration
  is claimed**.

`POST /fhir/export/{case_id}` response (`FhirExportResponse`):

```json
{
  "export_id": "9b2f…-…",
  "case_id": "…",
  "session_id": "…",
  "status": "succeeded",
  "destination": "local",
  "error": null,
  "attempted_at": "2026-09-08T…",
  "succeeded_at": "2026-09-08T…",
  "created_at": "2026-09-08T…",
  "bundle": { "resourceType": "Bundle", "type": "collection", "entry": [ … ] },
  "message": "FHIR R4 Bundle generated from the confirmed case."
}
```

Failed attempts return the same shape with `status: "failed"`, `bundle: null`
and a populated `error`.

`GET /fhir/export/{case_id}` response (`FhirExportStatusResponse`) — the
bundle payload is not repeated here:

```json
{
  "case_id": "…",
  "session_id": "…",
  "export": {
    "export_id": "9b2f…-…",
    "case_id": "…",
    "session_id": "…",
    "status": "succeeded",
    "destination": "local",
    "error": null,
    "attempted_at": "2026-09-08T…",
    "succeeded_at": "2026-09-08T…",
    "created_at": "2026-09-08T…",
    "bundle": null,
    "message": "FHIR R4 Bundle generated from the confirmed case."
  }
}
```

---

## Contract-change policy

Any change to a request/response shape must be mirrored in:

- `backend/app/schemas/*` (Pydantic, authoritative for the backend),
- `frontend/src/types/index.ts` (transport types),
- this document.

The **canonical internal clinical case model** lives in `docs/DATA_MODEL.md`
and is the interchange format used before FHIR conversion.
