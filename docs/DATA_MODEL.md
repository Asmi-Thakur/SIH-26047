# MediKiosk — Data Model

## Authoritative vs transport types

| Kind | Where it lives | Role |
|---|---|---|
| **Canonical clinical case** | `docs/DATA_MODEL.md` (this file) §1 | Internal interchange format combining interview + documents + triage; input to FHIR mapping. **Authoritative.** |
| **ORM models** | `backend/app/models/` (SQLAlchemy) | Persistence layer. Class ↔ table mapping in §3. |
| **Pydantic schemas** | `backend/app/schemas/` | HTTP transport (request/response validation). |
| **TypeScript types** | `frontend/src/types/index.ts` | Frontend transport types, mirrored from the Pydantic/API contract. UI never invents domain shapes. |

Rule: the canonical case model is defined once; Pydantic and TypeScript types
are *views* of it for transport, and FHIR resources are a *mapping* of it.

---

## 1. Canonical internal clinical case model

The case is assembled as the patient progresses; it is what the summary
generator, physician console and FHIR mapper consume.

```json
{
  "case_id": "case_…",
  "patient": {
    "patient_id": "pat_001",
    "token": "A-104",
    "name": "Demo Patient",
    "age": 52,
    "sex": "male",
    "preferred_language": "hi"
  },
  "consent": {
    "granted": true,
    "purposes": ["clinical_intake", "document_processing", "record_sharing"],
    "timestamp": "2026-09-06T10:42:00+05:30"
  },
  "chief_complaint": {
    "text": "Chest pain for two days",
    "onset": "2 days ago",
    "source": "patient_voice",
    "confidence": 0.94
  },
  "hpi": {
    "location": "central chest",
    "character": "pressure",
    "severity": 7,
    "radiation": "left arm",
    "aggravating": ["walking"],
    "relieving": ["rest"],
    "associated_symptoms": ["breathlessness", "sweating"]
  },
  "past_history": [],
  "surgical_history": [],
  "medications": [],
  "allergies": [],
  "family_history": [],
  "personal_history": {},
  "review_of_systems": {},
  "ayush": null,
  "documents": [],
  "timeline": [],
  "triage": {
    "priority": "urgent",
    "rules_triggered": ["CHEST_PAIN_PLUS_DYSPNEA"]
  }
}
```

Sections distinguish provenance: `patient_reported`, `document_extracted`,
`physician_confirmed`. Never overwrite confirmed content silently
(case versioning, see `case_versions` table).

---

## 2. Enumerations (planned constants)

- Session state: `welcome, identity, consent, chief_complaint, hpi, past_history, medications, allergies, family_history, personal_history, ros, ayush, documents, summary_review, submitted, closed`
- Document types: `prescription, lab_report, discharge_summary, imaging_report, other, unknown`
- Document processing status: `uploaded, processing, completed, failed`
- Triage priority: `routine, urgent`  ·  Alert status: `active, acknowledged`
- Case status: `draft, physician_edited, confirmed`
- User roles: `doctor, triage, admin`
- Input modes: `voice, touch, manual`

---

## 3. Database tables (Phase 1 — PostgreSQL)

Migration: `backend/alembic/versions/0001_initial_schema.py` (run `alembic upgrade head`).
Conventions: UUID primary keys (Python-generated), timezone-aware timestamps
(`TIMESTAMPTZ`, `server_default = CURRENT_TIMESTAMP`), flexible structured
payloads stored as `JSONB` on PostgreSQL (portable JSON variant elsewhere).

| Class | Table | Purpose | Key columns |
|---|---|---|---|
| `Patient` | `patients` | Demographics | `external_token` UNIQUE, name, age, sex, preferred_language |
| `PatientSession` | `sessions` | One intake journey | patient_id FK, `state`, mode, department, started/completed_at, is_demo |
| `Consent` | `consents` | Consent decision per session | session_id FK (unique), `granted`, purposes JSONB, consent_text_version, revoked_at |
| `Answer` | `answers` | Every question answer | session_id FK, question_id, input_mode, raw_answer, structured_value JSONB, confidence, source |
| `Document` | `documents` | Uploaded medical doc | session_id FK, file_name, mime_type, sha256, document_type, storage_path, processing_status |
| `TriageAlert` | `triage_alerts` | Red-flag alert | session_id FK, priority, rules_triggered JSONB, message, status, acknowledged_at |
| `CaseSummary` | `case_summaries` | Current summary record | session_id FK (unique), status, content JSONB, draft_version, confirmed_by, confirmed_at |
| `CaseVersion` | `case_versions` | Immutable versions | case_summary_id FK, version_number, status, content JSONB, edited_by |
| `User` | `users` | Staff (doctor/triage/admin) | username UNIQUE, role, display_name |
| `AuditLog` | `audit_logs` | Audit trail | actor_type, actor_id, action, entity_type, entity_id, details JSONB |
| `FhirExport` | `fhir_exports` | FHIR export attempts | session_id FK, status, bundle JSONB, destination, error, timestamps |
| `SyncQueue` | `sync_queue` | Offline sync queue | session_id, operation, payload JSONB, attempts, status |

### Relationships

```text
patients 1 ─── * sessions 1 ─── 1 consents
                       ├── * answers
                       ├── * documents
                       ├── * triage_alerts
                       ├── 1 case_summaries 1 ─── * case_versions
                       ├── * fhir_exports
                       └── * sync_queue
users * ─── (actor) audit_logs
```

Deliberately **not** modelled yet (future phases, per spec §26): `questions`
(content lives in version-controlled `clinical/` files), `document_extractions`,
`document_entities`, `clinical_timelines` (derived views built later).

---

## 4. JSONB usage policy

Use `JSONB` only for genuinely flexible structured data:

- consent `purposes`,
- answer `structured_value` (LLM-extracted, schema varies by question),
- triage `rules_triggered`,
- case summary/version `content` (canonical case sections),
- audit `details`,
- fhir export `bundle`,
- sync queue `payload`.

Everything with a stable shape is a real column. The portable column type is
`JSON().with_variant(postgresql.JSONB(), "postgresql")` (see `backend/app/db/base.py`).
