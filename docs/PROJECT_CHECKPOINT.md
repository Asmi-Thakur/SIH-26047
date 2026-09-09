# MediKiosk — PROJECT CHECKPOINT / HANDOFF

> Last updated: 2026-09-09 (**FINAL RELEASE PASS** — repo audited/cleaned, release smoke
> test added, README publish instructions verified)
> · Maintain this file as the project grows. If it
> diverges from the actual files, **the files win** — re-sync this document.
> New AI agents: read `docs/PROTOTYPE_BUILD_SPEC.md` (source of truth for
> product behaviour), `ARCHITECTURE.md`, `docs/API_CONTRACT.md`,
> `docs/DATA_MODEL.md`, `docs/DECISIONS.md`, and this checkpoint **before**
> making changes.

---

## PROJECT

- **Project:** MediKiosk — AI-assisted patient clinical intake platform
- **Competition:** Smart India Hackathon 2026
- **Problem statement:** SIH26047 — Patient Case-Taking Software
- **Organization:** Ministry of Ayush, All India Institute of Ayurveda
- **Category/Theme:** Software / Smart Automation
- **Root folder on this machine:** `C:\Users\advai\Desktop\HAC` (Windows) ·
  this working copy: `HAC/HAC` (macOS ARM64)
- **Goal:** a working demo of one patient journey — patient self-serves
  history (voice or touch) + scans old documents → physician-ready editable
  case summary → consent-aware FHIR/ABDM export. **AI assists; it never
  diagnoses.** Deterministic shell first, AI inside.

---

## COMPLETED (all verified — no 501 endpoints remain)

### Phase 4/2 — Real OCR + document→case integration (done 2026-09-09, verified)
- **Real PaddleOCR runs on this host.** The backend venv is now
  **CPython 3.12.14** (created with `uv`; the old 3.14/Windows venv was
  replaced). `backend/requirements-ocr.txt`: `paddlepaddle==3.3.1 +
  paddleocr==3.7.0 + pypdfium2 + pillow` — verified natively on macOS ARM64.
  A synthetic printed lab report OCR'd through the REAL API stack at
  **0.9955 mean confidence**; the seeded demo lab report processes with the
  real engine (`provider: paddleocr, mocked: false`).
- `services/ocr/registry.py` — `OCR_PROVIDER=auto` (default): real engine
  when importable, else honest mock; `paddleocr` forces real and **raises**
  if missing; `mock` forces the labelled simulation. Config default changed
  from `paddleocr` → `auto` (ADR-020).
- `services/ocr/paddle.py` — real engine behind `OCRProvider` (`app/
  integrations/base.py`); lazy heavy imports; **numpy** image input
  (PaddleOCR 3.x rejects raw bytes); PDFs rasterised page-by-page
  (pypdfium2, ~144 dpi); per-line text/confidence/box; page count.
- `services/ocr/mock.py` — deterministic fixture provider, NEVER reads the
  bytes, labelled `mocked: true` everywhere (payload `engine_note`, column,
  API message, UI "Simulated OCR" badge, summary `[mocked OCR]`).
- `services/ocr/extract.py` — deterministic classifier (spec §16.3) +
  clinical extractor: lab tests (value/unit/reference-range/`status`;
  ranges only from the document — `unknown` when absent, spec §21),
  medication lines, condition mentions; every row carries `source_text`.
- `services/ocr/service.py` + `api/documents.py` — **reprocess real**:
  consent-gated (409 without GRANTED consent), lifecycle
  `uploaded|completed|failed → processing → completed|failed` (409 while
  mid-flight), `OCR_COMPLETED` audit, failure → persisted `failed` +
  `last_error` returned readably (never a bare 5xx), retryable.
- Migration `0002_document_ocr_columns`: documents gains nullable
  `extraction, page_count, ocr_provider, ocr_mocked, processed_at,
  last_error`. Schemas: `DocumentRead` extended,
  `DocumentReprocessResponse` new (API_CONTRACT updated).
- **Case integration (existing builder, no parallel model):** completed
  documents enrich canonical `documents` (+ provider/mock/page/abnormal
  data), `investigations` (completed lab/imaging), timeline
  (`document_extracted` abnormal-value events), `provenance
  .document_extracted`; summary `prior_investigations` shows flagged values.
- Tests: `test_ocr.py` (13): unknown doc, consent gates (none + declined),
  mock success/labels/transitions, PDF handling, failure→failed+error+retry,
  real-provider seam (configured-but-missing raises; auto→real when
  available), multi-page PDF, safe reprocess, case provenance + abnormal
  flags + missing-info states, classifier/extractor units.

### Phase 8 — AYUSH Dashavidha (done 2026-09-09, verified)
- Bank v2: `ay_001–ay_011` (bilingual, structured choices + one optional
  note) with `department_for: ["ayush"]`; `applicable_questions` gained the
  department gate; the engine appends the `ayush` section after ROS **only**
  for `department: ayush` sessions (ADR-021).
- Canonical `case.ayush = {collected, department, items[{text, source,
  question_id, field}], disclaimer}`; summary `ayush_history` renders the
  labelled items ("Not collected" when absent). Structured capture only —
  never an Ayurvedic diagnosis (spec §14.3).
- Frontend: Identity department picker (General/AYUSH); section order
  updated; CasePage `ayush_history` section already renders the summary.
- Tests: `test_ayush.py` (5): department gating both ways, full AYUSH
  interview completes, `ayush` block + provenance + summary + disclaimer,
  structured-only bank assertions.

### Demo seed + judging polish (done 2026-09-09, verified)
- `scripts/seed_demo_data.py` — repeatable synthetic seed through REAL
  services: **A-901** urgent chest pain+breathlessness (deterministic
  `CHEST_PAIN_PLUS_DYSPNEA` alert verified), **A-902** routine fever+cough
  with an OCR-processed lab report (real engine on this host; labelled mock
  otherwise), **A-903** AYUSH joint pain with 11 Dashavidha items. Wipes its
  previous rows each run; pre-creates draft cases; reports the actual OCR
  provider used. No real patient data anywhere.
- Frontend: real **ReviewPage** (P09 — complaint/meds/allergies/documents
  confirmation with Edit + Send), real **DocumentsPage** (P07/P08 — upload →
  reprocess → processing stages → abnormal-value card + honest
  "Simulated/Real OCR" badge), CompletePage urgent notice (P10) + new-patient
  loop, CasePage documents card shows `provider · mocked · flags`,
  Identity department picker. **en/hi i18n parity fixed: 157 = 157 keys**
  (16 dashboard/triage keys were missing in hi.ts — fell back to English).
- README roadmap/demo-mode sections de-staled (no "future OCR" claims).

### Phase 7 — FHIR export (done, verified — do not redo)
- `services/fhir/mapper.py` provenance-preserving R4 Bundle; Condition ONLY
  from `physician_confirmed`; 409 `case_not_confirmed`/`consent_required`
  gates; `fhir_exports` persistence; "Export FHIR" on confirmed CasePage.

### Phases 1–6 (done, verified)
- Foundation (sessions/consent/Alembic/12 tables), deterministic bilingual
  touch interview (voice-optional), deterministic red-flag triage, doctor
  queue, unified case + source-labelled draft, physician edit/confirm
  (immutable), document upload core, LLM extraction seam (mock +
  key-gated Gemini), speech endpoints (mock, labelled).

---

## CURRENT STATE

**The entire MVP pipeline is real and tested.** Backend **59 pytest pass**;
frontend **16 vitest pass** + typecheck + build (all re-run 2026-09-09).
**No 501 endpoints remain.** Honest labels: speech/LLM/OCR-fallback are
mocked and labelled; OCR is REAL when the paddle packages are installed;
FHIR destination is `local` (no live ABDM claim).

**Environment note for new machines:** backend venv must be Python
3.10–3.12 for real OCR (`uv venv --python 3.12`); `requirements-ocr.txt`
is optional — without it everything still works via the labelled mock.
Windows hosts use `.venv\Scripts\python.exe`.

**Exact place to resume:** judging rehearsal (seed → walk the three cases →
confirm → export FHIR). Optional extras listed at the end of
`docs/AI_HANDOFF.md` §6.

---

## FILES (most relevant — new/changed this pass in bold)

| File / dir | Purpose | Status |
|---|---|---|
| `backend/app/services/ocr/*` | registry, real paddle, mock, extract, service | **created (4/2)** |
| `backend/app/api/documents.py` | upload/GET enriched + reprocess real | **modified (4/2)** |
| `backend/app/schemas/documents.py` | DocumentRead extended + ReprocessResponse | **modified (4/2)** |
| `backend/app/models/clinical.py` | OCR result columns | **modified (4/2)** |
| `backend/alembic/versions/0002_document_ocr_columns.py` | migration | **created (4/2)** |
| `backend/requirements.txt` / `requirements-ocr.txt` | deps + optional real-OCR stack | **modified/created** |
| `backend/app/tests/test_ocr.py`, `test_ayush.py` | 18 new tests | **created** |
| `backend/app/tests/test_health.py`, `conftest.py` | no-501 update; OCR_PROVIDER=mock in tests | **modified** |
| `backend/app/services/cases/builder.py`, `summary/generator.py` | document + ayush integration | **modified (4/2, 8)** |
| `backend/app/clinical/{schemas/question.py, questions/loader.py, questions/bank/questions.json}` | department gate + bank v2 | **modified (8)** |
| `backend/app/services/dialogue/engine.py` | department-aware progress | **modified (8)** |
| `backend/app/config.py`, `.env.example` | OCR_PROVIDER=auto | **modified (4/2)** |
| `scripts/seed_demo_data.py` | repeatable 3-case demo seed | **created** |
| `frontend/src/pages/patient/{DocumentsPage,ReviewPage,CompletePage,IdentityPage}.tsx` | real screens + department picker | **modified** |
| `frontend/src/pages/doctor/CasePage.tsx` | documents card w/ OCR provenance | **modified** |
| `frontend/src/types/index.ts`, `services/api.ts` | mirrored contract | **modified (4/2)** |
| `frontend/src/i18n/{en,hi}.ts` | +55 keys; **full parity 157=157** | **modified (4/2/8)** |
| `frontend/src/pages/patient/documents.test.tsx` | DocumentsPage tests | **created** |
| `docs/{API_CONTRACT,DECISIONS,AI_HANDOFF,PROJECT_CHECKPOINT}.md`, `README.md` | docs synced (ADR-020/021) | **modified** |

---

## IMPORTANT REQUIREMENTS & DECISIONS

- **AI assists, never diagnoses.** Physician confirms everything. Sections
  carry `patient_reported` / `document_extracted` / `physician_confirmed`.
- **Deterministic shell first, AI inside** (spec §60): touch intake works
  with all AI down; triage is rule-based only (ADR-015).
- **Provider abstractions:** speech/LLM/OCR behind `app/integrations/base.py`
  protocols + registries; OCR fallback is always honestly labelled (ADR-020);
  FHIR is a real local bundle, ABDM stays an adapter boundary (ADR-011/019).
- **Consent gating:** interview requires a decision row; document
  processing requires GRANTED consent; FHIR export requires granted consent
  + confirmed case.
- **Secrets backend-only**; CORS allow-list; no VITE_* secrets.
- **DB conventions:** UUID PKs, tz-aware UTC, JSONB-variant JSON, naming
  convention, Alembic migrations (now 0001 + 0002).
- **Wire contract:** Pydantic authoritative; mirror in
  `frontend/src/types/index.ts` + `docs/API_CONTRACT.md`; wire ids are
  `session_id`/`case_id` (ORM column `id`).
- **i18n:** flat dot-keyed; en.ts and hi.ts keys are now verified identical
  (157 = 157) — keep it that way.
- **Demo data:** synthetic only (tokens A-901/902/903, "Demo" patients).

---

## DO NOT CHANGE

- The FHIR mapper/export implementation (ADR-019) — complete + tested.
- The provider registry pattern and the OCRProvider/mock semantics of
  ADR-020 (labels, `auto` fallback, raise-on-forced-missing).
- The interview state machine semantics (ADR-014) and triage rules (ADR-015).
- `docs/PROTOTYPE_BUILD_SPEC.md` content (append-only if needed).
- Error envelope, dependency injection, DB naming/migration approach.
- Working tests — extend, never delete to make suites pass.

---

## KNOWN ISSUES

- PaddleOCR model files download on first real use (~10 s; cache via
  `PADDLE_PDX_CACHE_HOME`); first OCR call is slower than later ones.
- Deprecation warnings from Starlette TestClient (harmless).
- Docker not installed on this dev machine — compose remains
  YAML-validated only; sqlite used for tests/smoke/seed here.
- The Docker backend image does not yet install `requirements-ocr.txt`
  (add it to the Dockerfile if real OCR is wanted inside compose; the
  labelled mock keeps the demo working without it).
- `docs/PROTOTYPE_BUILD_SPEC.md` §50 milestone list predates the actual
  phase numbering used in this repo (2b/3b/3c/3d/4/2 etc.) — harmless.

---

## RELEASE PASS (2026-09-09) — repository is publish-ready

- **Blocker sweep:** no TODO/FIXME/501/placeholder/debug output in committed
  source; no dead routes or dead UI actions.
- **Security scan:** no secrets in source (only `replace_me` defaults and
  empty key vars in `.env.example`); frontend uses only the public
  `VITE_API_BASE_URL`; `.env` gitignored; seed data is explicitly synthetic
  ("Demo Patient"); generated `storage/uploads/*` and scratch DBs removed
  and gitignored.
- **Repo cleanup:** removed stale pre-OCR `MediKiosk_SIH26047.zip`, empty
  zip-artifact `clinical/` + `demo/` dirs, generated uploads; `.gitignore`
  extended (uploads, `*.sqlite`, `.freebuff`, zips).
- **Reproducibility verified:** fresh DB → `alembic upgrade head` (0001+0002)
  → `scripts/seed_demo_data.py` → servers up, all green on SQLite.
- **New: `scripts/release_smoke_test.py`** — 22 API checks walking the three
  demo journeys (urgent triage→confirm→export→immutability-409; routine+OCR
  provenance+abnormal flag; AYUSH `canonical.ayush`). **All 22 PASS.**
- **README rewritten for release:** no-Docker quickstart (Option B2), OCR
  setup section, correct repo layout, smoke-test instructions, honest
  mock/ABDM statements.

## NEXT STEPS (ordered)

1. `git init` + initial commit + push to the public repository (the only
   remaining publish step — done locally, not pushed from this machine).
2. Judging rehearsal with the seed (see AI_HANDOFF §6).
3. Optional: analytics dashboard (spec §49), demo-reset button, kiosk
   auto-return timeout (spec §47).
4. Optional: real STT/TTS vendor behind `SpeechProvider`; Gemini-keyed
   summary drafting behind the LLM seam (deterministic draft stays default).
5. Optional: offline queue (spec §30) — the last unbuilt spec milestone.

---

## READY-TO-COPY CONTINUATION PROMPT

> This is an existing, completed-MVP MediKiosk project (SIH 2026, PS 26047) —
> do NOT start from scratch or redo finished phases.
>
> **Verified state (2026-09-09, release pass):** backend 59 pytest; frontend
> 16 vitest + typecheck + build; release smoke test 22/22 PASS; **no 501
> endpoints**. Real PaddleOCR runs (py3.12 venv,
> `requirements-ocr.txt`; verified ~0.99 confidence end-to-end) with an
> honestly-labelled mock fallback (`OCR_PROVIDER=auto`, ADR-020);
> `POST /documents/{id}/reprocess` drives the full lifecycle into the
> canonical case with `document_extracted` provenance + abnormal flags;
> AYUSH Dashavidha section (ADR-021) feeds `case.ayush`; repeatable demo
> seed `scripts/seed_demo_data.py` (A-901 urgent / A-902 routine+lab /
> A-903 AYUSH); FHIR export confirmed-case-gated (ADR-019, local bundle —
> no live ABDM claim); en/hi i18n at full parity.
>
> **Rules:** deterministic triage never LLM-overridden; consent gates;
> question-bank-only; structured LLM output; `mocked: true` labelling;
> secrets backend-only; confirmed cases immutable; FHIR only after
> confirmation; Pydantic schemas mirrored in `frontend/src/types/index.ts`
> + `docs/API_CONTRACT.md`; wire ids `session_id`/`case_id`; en/hi keys
> identical; synthetic data only.
>
> **Working style:** inspect first, smallest coherent slice, run
> `cd backend && .venv/bin/python -m pytest -q` and `cd frontend && npm run
> typecheck && npm test && npm run build` after every slice, keep
> `docs/PROJECT_CHECKPOINT.md` + `docs/AI_HANDOFF.md` current, stop at clean
> points.
