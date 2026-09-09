# MediKiosk — Architecture Decision Log

How to use this file: when you make a consequential architectural decision,
**append** an entry here instead of silently changing course. Note what changed
and why, so future agents do not "rediscover" and revert it.

Format of an entry: **Decision — context — consequence.**

---

## ADR-001 · FastAPI (Python) backend, not Node

- **Context:** the product needs heavy AI/OCR/ML ecosystem work (LLM calls,
  PaddleOCR/OpenCV, speech), which is far more natural in Python; the UI layer
  is best served by the React ecosystem.
- **Consequence:** FastAPI + Pydantic v2 + async SQLAlchemy. Frontend (React)
  never talks to vendor SDKs directly — it talks to our API.

## ADR-002 · PostgreSQL 16 with async SQLAlchemy 2 + Alembic

- **Context:** relational core (patients, sessions, consents, audit) plus
  flexible AI outputs (JSONB). Alembic gives versioned migrations.
- **Consequence:** UUID PKs, timezone-aware timestamps, JSONB only where
  flexibility is real (`docs/DATA_MODEL.md` §4). Async engine throughout;
  `DATABASE_URL` default is `postgresql+asyncpg://…`.

## ADR-003 · Provider abstraction for every external AI capability

- **Context:** LLM, speech, OCR and FHIR/ABDM vendors can change or fail; demo
  mode must run with no paid APIs and no internet.
- **Consequence:** `SpeechProvider`, `LLMProvider`, `OCRProvider`,
  `HealthRecordAdapter` are Python Protocols in `backend/app/integrations/`.
  Configuration selects the implementation; `DEMO_MODE=true` selects mocks.
  Never call a vendor SDK outside an adapter.

## ADR-004 · Secrets live only in the backend

- **Context:** the MediParse reference project shipped a client-side Gemini key;
  we deliberately do **not** copy that.
- **Consequence:** `.env` (backend) holds keys; `.gitignore` excludes it; no
  `VITE_*` secret variables exist; CORS is an explicit allow-list.

## ADR-005 · A canonical internal clinical case model is the interchange format

- **Context:** interview, documents and triage feed one physician-ready case;
  FHIR is only one output format.
- **Consequence:** a single case shape (`docs/DATA_MODEL.md` §1) is the input to
  summary generation and FHIR mapping. Pydantic and TypeScript types are views
  of it. FHIR mapping never happens directly from DB rows or UI state.

## ADR-006 · Deterministic safety rules, not LLM judgement

- **Context:** red-flag escalation must be reliable and explainable.
- **Consequence:** triage is a rule engine over normalized symptoms (Phase 3);
  the LLM never decides priority and never communicates a diagnosis to a patient.

## ADR-007 · Physician confirmation gates export

- **Context:** nothing may leave for FHIR/HIS that a clinician has not seen.
- **Consequence:** case lifecycle `draft → physician_edited → confirmed`;
  `confirm` creates an immutable `case_versions` row and only then triggers
  export (Phase 6–7).

## ADR-008 · Demo mode is a first-class configuration

- **Context:** judging environments are unpredictable.
- **Consequence:** `DEMO_MODE=true` is the default; mock providers return
  deterministic fixtures so the whole flow repeats consistently with zero keys.

## ADR-009 · No autonomous diagnosis, ever

- **Context:** SIH26047 is clinical history intake; the spec forbids chatbot-like
  diagnosis and the product must be defensible.
- **Consequence:** UI/UX copy, prompts, and validation all enforce
  "AI assists, the physician decides." Summary sections are labelled
  `patient_reported` / `document_extracted` / `physician_confirmed`.

## ADR-010 · Question bank and rules are content, not code

- **Context:** clinical workflows must be editable without redeploying the UI.
- **Consequence:** `clinical/` holds version-controlled JSON/YAML question banks
  and rules (Phase 2+); the engine reads them, the UI renders generic cards.

## ADR-011 · FHIR/ABDM behind a `HealthRecordAdapter`

- **Context:** ABDM credentials/onboarding should not block the demo.
- **Consequence:** implement `MockHealthRecordAdapter` → `FHIRServerAdapter`
  (HAPI) → `ABDMAdapter` progressively; core logic depends on the interface.

## ADR-012 · Deterministic shell first; AI inside

- **Context:** spec §60; every external service can fail.
- **Consequence:** Phase 1 ships no AI at all — only boundaries. A patient can
  (eventually) complete intake by touch with AI fully down.

## ADR-013 · Session lifecycle semantics (Phase 2)

- **Context:** `POST /sessions` needs predictable, deterministic behaviour;
  the spec does not pin state at creation.
- **Decision:** a session is created in state `identity` (Welcome is
  pre-session UI). Patients are find-or-created by `external_token` when a
  token is supplied, otherwise a walk-in patient row is created. `language`
  is stored on the patient row. Consent is an upsert of a single `consents`
  row per session (revising a decision updates it) and emits
  `SESSION_CREATED` / `CONSENT_GRANTED` / `CONSENT_DECLINED` audit events.
- **Consequence:** session creation and consent never depend on AI; they are
  plain transaction+audit work the kiosk can always do. Advancing past
  `identity` is the interview module's job (ADR-010).

## ADR-014 · Deterministic touch interview (Phase 2b)

- **Context:** the interview must never be a free-running LLM chat (spec §8);
  a patient must finish a history with all AI down.
- **Decision:** progress is *derived from recorded answers* — per section in
  fixed order, a section completes when every applicable question is
  answered. Applicability is deterministic: questions declare
  `for_complaints` and are skipped unless the recorded chief complaint code
  matches (SOCRATES-style HPI). The session `state` column mirrors progress
  for dashboards/resume. The engine accepts only the expected next question
  (`409 question_not_current`) and only known choice codes (`422`).
  Interview endpoints require a recorded consent row (`409 consent_required`)
  so consent-gating is enforced at the boundary.
- **Consequence:** the interview works fully offline with zero AI. Adaptive
  questioning, voice and LLM extraction later *decorate* this shell rather
  than replace it.

## ADR-015 · Triage is deterministic rule content, never the LLM (Phase 3b)

- **Context:** spec §13 and §53 (Mistake 3: “Letting LLM decide emergency
  severity”). Emergency flags must be reproducible and auditable.
- **Decision:** rules are content (`clinical/rules/rules.json`, validated by
  Pydantic) evaluated over structured symptom buckets derived from answers
  (`chief_complaint`←cc_001, `associated`←hpi_004, `severity`←hpi_003).
  Alerts are created inside the interview answer path, one per (session,
  rule) while active, with `RED_FLAG_CREATED` audit events; acknowledging
  clears the active queue.
- **Consequence:** triage works fully offline and never depends on model
  availability or prompt drift. New rules are data edits + unit tests.

## ADR-016 · Speech pipeline: mock provider first, vendors later (Phase 3c)

- **Context:** demo environments have no ASR/TTS keys; the full browser audio
  pipeline must still be demonstrable (spec §60).
- **Decision:** `SPEECH_PROVIDER` selects the provider (default `mock`); the
  registry is the only place vendors are named. Mock transcribe returns a
  deterministic bilingual sample and mock synthesize returns a silent WAV;
  every response carries `mocked: true`. Real vendors (Sarvam,
  IndicConformer/Whisper) implement the same SpeechProvider protocol.
- **Consequence:** capture→upload→endpoint→transcript works end-to-end with
  no keys; swapping in real STT changes nothing above the provider.

## ADR-017 · LLM extraction: structured seam, mock default, Gemini gated (Phase 3d/2)

- **Context:** the spec wants structured clinical extraction from free text;
  demo environments have no model keys; AI must never produce free-form
  output that bypasses schemas (spec §9/§53).
- **Decision:** `/api/llm/extract` returns one fixed shape (`complaint[]`,
  `duration`, `conditions[]`, `medications[]`, `missing_information[]`).
  `LLM_PROVIDER=mock` uses a deterministic keyword extractor (labelled
  `mocked: true`); `gemini` is key-gated and any malformed/failed response
  falls back to the deterministic extractor. Extraction is heuristic
  patient-reported structure — never a diagnosis.
- **Consequence:** the structured contract is stable before any real model is
  attached, and demo truth is never overstated.

## ADR-018 · Unified case: canonical assembly + get-or-create summary + confirm-gated export (Phase 6)

- **Context:** voice/touch/OCR/AYUSH data must converge into ONE physician-
  reviewable case (spec §27–30, §57); the physician console needs an editable
  draft and a lock; nothing may leave for FHIR before confirmation (ADR-007).
- **Decision:** the canonical case (`docs/DATA_MODEL.md` §1) is *re-assembled
  from recorded facts on every read* — never cached stale — by
  `services/cases/builder.py`, which maps answers → sections, attaches
  `source` provenance to every item, builds the timeline (answers + document
  uploads + triage alerts) and derives `missing_information` from
  unanswered sections. A “case” is the existing `case_summaries` row: created
  lazily on first physician read (`GET /cases/by-session/{id}`) with a
  deterministic summary draft + immutable `case_versions` v1; `case_id` =
  `case_summaries.id` and is exposed on `GET /sessions/{id}` once it exists.
  Physician edits PATCH `summary` (→ `physician_edited`, new version,
  `CASE_EDITED` audit); confirm POSTs (→ `confirmed`, `confirmed_at`,
  immutable version, `CASE_CONFIRMED` audit). Confirmed cases reject further
  edits/confirmation with 409 — never silently overwritten. FHIR export
  (Phase 7) requires `status == confirmed`.
- **Consequence:** the physician console is real (AI draft → edit → verify →
  confirm), offline-safe, and every piece of the case keeps its source.
  Summary draft is deterministic (`mock`) and honestly labelled; a key-gated
  LLM may later produce the same shape, with the deterministic draft as
  fallback (ADR-017).

## ADR-019 · FHIR export: confirmation-gated, provenance-preserving mapper (Phase 7)

- **Context:** the last 501s (`POST/GET /api/fhir/export/{case_id}`) must turn
  real without violating ADR-007 (nothing leaves before physician
  confirmation), ADR-009 (AI never diagnoses) or ADR-011 (ABDM stays behind an
  adapter boundary).
- **Decision:** `services/fhir/mapper.py` maps the **confirmed canonical
  case** (re-assembled from recorded facts, ADR-005/018) to a deterministic
  FHIR R4 `Bundle` (`type: collection`, `urn:uuid` ids derived via uuid5 from
  the case id). Resources: Patient, Encounter, Consent, Composition,
  Observation(s), AllergyIntolerance, MedicationStatement, DocumentReference.
  Every resource carries a `source` extension normalised to
  `patient_reported` / `document_extracted` / `physician_confirmed`, and
  Composition narrative sections repeat the source inline — provenance
  survives the hop to FHIR consumers. **Condition resources are created only
  from `physician_confirmed` items**; patient-reported problems stay
  Observations, so no AI suggestion or self-report can silently become a
  diagnosis. `POST /fhir/export/{case_id}` refuses unconfirmed cases (409
  `case_not_confirmed`) and ungranted consent (409 `consent_required`); every
  attempt is persisted to `fhir_exports` (`pending → succeeded|failed`, with
  `destination` and timestamps) plus `FHIR_EXPORTED` / `FHIR_EXPORT_FAILED`
  audit events; a mapper failure yields a `failed` row (retryable), never a
  500. `GET` returns the last attempt. `destination` is `local` — no live
  ABDM/FHIR-server push is claimed until a `HealthRecordAdapter`
  implementation exists (ADR-011).
- **Consequence:** the confirmed record can leave the system in a valid,
  provenance-labelled bundle while the safety gates stay intact; swapping in a
  real FHIR server or ABDM later touches only the adapter, not the mapper or
  the router.

---

## ADR-020 · Real PaddleOCR behind OCRProvider with an honest labelled mock fallback (Phase 4/2)

- **Context:** `POST /documents/{id}/reprocess` was the last 501. PaddleOCR
  needs Python 3.10–3.12 (no paddlepaddle wheels for 3.13/3.14) and the
  original dev host ran 3.14 with no Docker. The project venv is now created
  with **CPython 3.12 (uv)**, where `paddlepaddle==3.3.1 + paddleocr==3.7.0
  + pypdfium2` install and run natively (macOS ARM64 verified: a synthetic
  printed lab report OCR'd at ~0.99 confidence through the real API stack,
  and the seeded demo lab report processes with the REAL engine).
- **Decision:** `OCR_PROVIDER=auto` (new default) runs the **real
  PaddleOCR** (`services/ocr/paddle.py`, lazy heavy imports, pypdfium2 PDF
  rasterisation) whenever the paddle packages are importable, and otherwise
  falls back to `services/ocr/mock.py` — a deterministic fixture that NEVER
  reads the uploaded bytes and is labelled `mocked: true` end-to-end
  (extraction payload, `ocr_mocked` column, API message, UI badge
  "Simulated OCR", summary `[mocked OCR]`). `OCR_PROVIDER=paddleocr`
  **raises** if the engine is missing (never silently degrades); `mock`
  forces simulation. PDFs are rasterised page-by-page; page counts and
  per-line confidences persist on the documents row (migration 0002:
  `extraction`, `page_count`, `ocr_provider`, `ocr_mocked`, `processed_at`,
  `last_error`). Classification is keyword-based (spec §16.3) and clinical
  extraction is deterministic (tests/meds/conditions with `source_text`,
  reference ranges only from the document, spec §21). Reprocess is
  consent-gated (409 without a granted consent) and a failed run persists
  `status=failed` + `last_error` (retryable, readable response — never a
  bare 5xx, mirroring the FHIR-export convention).
- **Consequence:** `document_extracted` provenance now feeds the canonical
  case (`documents`, `investigations`, abnormal-value timeline events,
  summary) through the existing builder — no parallel case representation.
  Honest demo truth: a judge can always tell simulated OCR from real OCR.

## ADR-021 · AYUSH Dashavidha as bank-gated questions feeding `case.ayush` (Phase 8)

- **Context:** spec §14 requires Dashavidha Pariksha / Ahara-Vihara capture
  for AYUSH OPDs, explicitly WITHOUT the system determining an Ayurvedic
  diagnosis or treatment (§14.3).
- **Decision:** the AYUSH section is **content, not code** (ADR-010):
  `ay_001–ay_011` in the question bank carry `department_for: ["ayush"]`;
  `applicable_questions` gained a department gate and the interview engine
  appends the `ayush` section after ROS only for sessions created with
  `department: "ayush"`. Answers flow through the existing engine/answer
  path (structured choices only; the single free-text question is optional
  and required=false). The canonical case builder emits `case.ayush =
  {collected, department, items[{text, source, question_id, field}],
  disclaimer}` and the summary renders an `ayush_history` section ("Not
  collected" when absent).
- **Consequence:** zero new endpoints, zero new tables, i18n unchanged in
  mechanics (bank prompts carry en+hi), and no AYUSH observation is ever
  converted into a modern diagnosis — provenance stays `patient_reported`.

---

## Open questions / revisit later

- **Async DB driver on Python 3.14:** `asyncpg` is preferred (ADR-002). If
  wheels are unavailable for a newer Python on Windows, fall back to
  `psycopg[binary]` async and record the swap here before changing code.
- **UUID generation:** Python-side `uuid.uuid4` today; revisit server-side
  `gen_random_uuid()` if bulk-insert patterns demand it.
