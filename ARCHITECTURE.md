# MediKiosk — Architecture

> Smart India Hackathon 2026 · PS 26047 · Patient Case-Taking Software
> Product source of truth: `docs/PROTOTYPE_BUILD_SPEC.md`
> Decision log: `docs/DECISIONS.md`

## Governing principle

**Build the deterministic shell first and add AI inside it.**

The system must keep working when the LLM is unavailable, speech recognition
fails, OCR fails, FHIR is offline, or the internet disappears. AI improves the
experience; it is never the single point of failure and never the source of
truth for safety decisions.

A second, non-negotiable principle: **the physician confirms the clinical
record**. Nothing is exported to FHIR/HIS without an explicit physician
`confirm` action, and no AI output is presented as a diagnosis.

## High-level responsibilities

| Layer | Responsibility |
|---|---|
| **Frontend** | Patient kiosk UI (voice + touch), physician console, triage view. Owns UX, input capture, client state, offline session cache. Never holds secrets. |
| **Backend (FastAPI)** | Session lifecycle, interview state, structured case model, deterministic safety rules, provider adapters, physician review API, FHIR mapping/export. Owns all API keys. |
| **Database (PostgreSQL)** | Canonical persistence: patients, sessions, consents, answers, documents, triage alerts, case summaries/versions, users, audit logs, FHIR exports, sync queue. |
| **Clinical content** | Version-controlled question bank + red-flag rules (future phases), stored separately from UI code. |
| **Integrations** | Speech, LLM, OCR, FHIR/ABDM — accessed only through provider interfaces. |

## Service boundaries

The backend is organised around coarse service boundaries that mirror the
product pipeline:

```text
api/          HTTP routers (thin): validation in, service call out
services/     Business logic: dialogue, speech, ocr, documents, summary,
              triage, fhir  (each behind a clear module boundary)
clinical/     Domain content: questions, rules, terminology, schemas
integrations/ Vendor adapters implementing provider Protocols
models/       SQLAlchemy ORM models (one file per domain group)
schemas/      Pydantic request/response schemas (transport layer)
db/           engine, session, declarative Base, JSONB helpers
prompts/      Version-controlled LLM prompt files (future phases)
```

Rules:

- Routers do not contain business logic.
- Services do not import vendor SDKs directly — they depend on interfaces.
- Models are not serialised straight to the API; Pydantic schemas are the
  transport contract.
- A single canonical internal *case* model (see `docs/DATA_MODEL.md`) is the
  interchange format before FHIR conversion.

## Provider abstraction philosophy

Every external capability is defined as a Python `Protocol` and resolved
through a factory that reads configuration:

```text
SpeechProvider    transcribe(audio, language) / synthesize(text, language)
                  -> MockSpeechProvider (DEMO_MODE) | Sarvam | IndicConformer (future)
LLMProvider       structured_extract(...) / next_question(...) / draft_summary(...)
                  -> MockLLMProvider (DEMO_MODE) | Gemini (future)
OCRProvider       extract(document) -> OCRResult
                  -> PaddleOCR (future) | Tesseract | EasyOCR | Donut (research)
HealthRecordAdapter  create_patient / submit_bundle / fetch_records
                  -> MockHealthRecordAdapter | FHIRServerAdapter | ABDMAdapter (future)
```

Implementations may be added per phase without touching callers.

## Future AI boundaries (not yet implemented)

- **LLM boundary** — only used for: transcript→structured-answer extraction,
  normalisation, selecting an *approved* next question, and summary drafting.
  Never used for consent, permissions, escalation, record finalisation or FHIR
  validity. Outputs are always validated against Pydantic schemas.
- **Speech boundary** — MediaRecorder in the browser → `POST /api/speech/transcribe`
  → provider adapter. TTS prompts read questions aloud. Demo mode returns
  deterministic fixtures.
- **OCR boundary** — document service owns validation/preprocessing/classification,
  then delegates to an OCR provider; output is passed through a structured
  extraction + provenance step before it touches the case model.
- **FHIR boundary** — the confirmed case is mapped to FHIR R4 resources by a
  dedicated mapper; export goes through a `HealthRecordAdapter`, never inline.

## Failure philosophy

Each external component can fail independently and the patient must not restart
the intake:

| Failure | Behaviour |
|---|---|
| Speech | Fall back to transcript text entry / touch answers |
| LLM | Continue deterministic question bank, store raw answers, template draft |
| OCR | Retry, try fallback provider, let physician inspect original |
| FHIR | Persist confirmed case, queue export, retry later |

## Deterministic shell (implemented in Phase 1)

- Session & consent lifecycle
- Canonical DB schema (12 tables)
- Case state machine boundaries (implemented in Phase 2+)
- Red-flag rule engine (Phase 3+)
- Health/status endpoints and CORS
- Provider Protocols + mock configuration (`DEMO_MODE=true` default)

## Frontend responsibilities

- Two UIs share one app: `/patient/*` (large touch targets, audio prompts,
  minimal text) and `/doctor/*` (dense, evidence-linked review console).
- All backend calls go through `src/services/api.ts` (single base URL from
  `VITE_API_BASE_URL`).
- Offline cache & sync queue live in the browser (`src/state`, `src/services/offline`)
  in later phases.

## Security posture (Phase 1 baseline)

- Secrets only in backend environment variables; `.env` git-ignored.
- Explicit CORS allow-list (backend settings).
- No upload endpoints implemented yet — document upload arrives with real
  validation in Phase 5.
- Synthetic demo data only; audit logging hooks exist from the schema.
