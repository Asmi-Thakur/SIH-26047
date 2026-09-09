# MediKiosk — AI Handoff & Verification Report

> Generated: 2026-09-07 · Updated: 2026-09-09 (Phase 4/2 real OCR + AYUSH +
> demo seed landed) · SIH 2026, PS 26047 (Patient Case-Taking Software).
> This project is passed between AI agents — **read this file, the checkpoint
> (`docs/PROJECT_CHECKPOINT.md`), and `docs/PROTOTYPE_BUILD_SPEC.md` before
> changing anything.** Files are authoritative over this document.

---

## 1. Audit verdict (VERIFIED, not assumed)

Re-verified on 2026-09-09 against the running code + test suites
(backend 59 pytest, frontend 16 vitest + typecheck + build — all green).

| Area | Verdict | Evidence |
|---|---|---|
| Session + consent API | ✅ Real | `POST/GET /api/sessions`, consent upsert, audit; tests |
| Deterministic touch interview | ✅ Real | `GET/POST /api/interview/*`; state machine over `answers`; bilingual bank |
| Deterministic triage | ✅ Real | `clinical/rules/evaluator.py`; alerts in the answer path; tests |
| Doctor queue/dashboard | ✅ Real | `GET /api/sessions` + Dashboard UI |
| Unified case + summary draft | ✅ Real | `services/cases/builder.py` + `services/summary/generator.py`; case tests |
| Physician review/edit/confirm | ✅ Real | CasePage UI; versioned edits; 409 on confirmed edits |
| Speech endpoints | ✅ Mock (labelled) | `POST /speech/transcribe|synthesize`; `mocked: true` |
| LLM extraction seam | ✅ Mock (key-gated Gemini) | `POST /llm/extract`; deterministic fallback labelled |
| Document upload + retention | ✅ Real | `POST/GET /api/documents/*`; original retained |
| **Document OCR / reprocess** | ✅ **REAL (PaddleOCR) + labelled mock fallback** | `POST /documents/{id}/reprocess` real; lifecycle + classification + deterministic extraction + provenance; 13 tests in `test_ocr.py` |
| FHIR export | ✅ Real (local bundle; ABDM = future adapter) | mapper + gating + `fhir_exports`; 7 tests |
| **AYUSH Dashavidha** | ✅ **Real (structured capture)** | bank `ay_001–ay_011` gated to `department: ayush`; `case.ayush` + summary; 5 tests |
| **Demo seed script** | ✅ **Real, repeatable** | `scripts/seed_demo_data.py` — 3 synthetic cases (urgent/routine+lab/AYUSH) |
| Real ASR/TTS vendors | ❌ NOT IMPLEMENTED | browser capture works; vendor providers pending |
| Offline queue (Phase 9) | ❌ NOT IMPLEMENTED | future work |

### Real-OCR verification detail (not assumed — actually executed)

- Environment: **CPython 3.12.14** venv (created with `uv`) on macOS ARM64.
  `paddlepaddle==3.3.1`, `paddleocr==3.7.0`, `pypdfium2==5.13.0`,
  `pillow==12.3.0` (`backend/requirements-ocr.txt`).
- A synthetic printed lab-report PNG OCR'd through the REAL API path
  (TestClient + sqlite + retained file): `provider: paddleocr`,
  `mocked: false`, mean confidence **0.9955**, 3–7 s, correct text incl.
  "Glucose 145 mg/dL (Ref 70-140) HIGH" → classified `lab_report`, abnormal
  flag raised, case `investigations` + `document_extracted` provenance
  populated, physician summary shows the flagged value.
- The seeded demo lab report (`scripts/seed_demo_data.py` → Pillow-rendered
  PNG) processes through the REAL engine on this host; on hosts without the
  paddle packages the same script runs the labelled mock instead — reported
  honestly in the seed output.

---

## 2. What changed in this pass (Phase 4/2 + 8 + demo)

- `services/ocr/{registry,mock,paddle,extract,service}.py` — provider
  registry (`auto|paddleocr|mock`), real engine (lazy imports, numpy input,
  PDF→pages via pypdfium2), honest mock, deterministic classifier +
  clinical extractor, reprocess lifecycle service (consent gate, status
  transitions, audits).
- `api/documents.py` — reprocess endpoint real; GET/upload responses carry
  `extraction/page_count/ocr_provider/ocr_mocked/processed_at/last_error`.
- `schemas/documents.py` — `DocumentRead` extended + `DocumentReprocessResponse`.
- `models/clinical.py` + `alembic/versions/0002_document_ocr_columns.py` —
  OCR result columns (nullable; existing rows untouched).
- `services/cases/builder.py` — completed documents enrich `documents`,
  `investigations`, timeline (abnormal-value events) and
  `provenance.document_extracted`; the `ayush` block per ADR-021.
- `services/summary/generator.py` — `prior_investigations` shows flagged
  values + `[document_extracted]`/`[mocked OCR]`; `ayush_history` renders.
- `clinical/schemas/question.py` + `loader.py` + `dialogue/engine.py` —
  `department_for` gate; `ayush` section appended for AYUSH departments.
- `clinical/questions/bank/questions.json` — version 2: 11 AYUSH questions
  (bilingual).
- Frontend: types mirrored (`DocumentExtraction`, `DocumentReprocessResponse`,
  richer canonical documents), `reprocessDocument()` client, real
  **DocumentsPage** (upload → reprocess → stages → results, "Simulated OCR"
  badge), real **ReviewPage** (P09), Complete urgent notice (P10), Identity
  department picker, CasePage documents card shows provider/mock/abnormal
  flags, **full en/hi i18n parity (157 = 157 keys)**.
- `scripts/seed_demo_data.py` — repeatable 3-case synthetic demo seed.
- Docs: API_CONTRACT (documents/interview/cases sections), DECISIONS
  (ADR-020, ADR-021), README roadmap honesty, this file, checkpoint.

---

## 3. What is MOCKED / BROKEN / MISSING

- **Mocked (all honestly labelled `mocked: true`):** speech STT/TTS;
  LLM extraction (Gemini is key-gated with deterministic fallback); OCR
  **fallback provider when the paddle packages are absent** — with
  `requirements-ocr.txt` installed, OCR is REAL (verified, see §1).
- **Broken:** nothing known. Deprecation warnings in tests are harmless.
- **Missing (ordered):** (1) real STT/TTS vendors behind the speech
  registry; (2) offline queue (Phase 9); (3) live ABDM/FHIR-server push
  behind `HealthRecordAdapter` (ADR-011 — not claimed); (4) Gemini-keyed
  summary drafting (the seam exists; deterministic draft is the default).
- **No live ABDM connectivity exists or is claimed.** Destination stays
  `local` (ADR-019).

---

## 4. Provider configuration

- **Speech:** `SPEECH_PROVIDER` (`mock` default). Registry:
  `app/services/speech/registry.py`.
- **LLM:** `LLM_PROVIDER` (`mock` default), `GEMINI_API_KEY` (backend-only).
- **OCR:** `OCR_PROVIDER` — `auto` (default: real engine when importable,
  else labelled mock), `paddleocr` (forces real; raises if missing),
  `mock` (forces simulation). Optional packages:
  `backend/requirements-ocr.txt` (py3.10–3.12 only).

---

## 5. Tests + exact run commands

```bash
# Backend (Python 3.12 venv at backend/.venv — recreated with uv on 2026-09-08):
cd backend && .venv/bin/python -m pytest -q        # 59 passed

# Frontend (node_modules reinstalled for macOS on 2026-09-08):
cd frontend && npm run typecheck && npm test && npm run build   # 16 passed

# Live local run WITHOUT Docker:
cd backend
DATABASE_URL="sqlite+aiosqlite:///./dev.db" .venv/bin/python -m alembic upgrade head
DATABASE_URL="sqlite+aiosqlite:///./dev.db" .venv/bin/python -m uvicorn app.main:app --reload
cd ../frontend && npm run dev          # http://localhost:5173

# Demo seed (3 synthetic cases; repeatable):
backend/.venv/bin/python scripts/seed_demo_data.py --db "sqlite+aiosqlite:///./demo.db"
```

Notes for new hosts:
- Recreate the backend venv with **Python 3.10–3.12** (3.13/3.14 have no
  paddlepaddle wheels): `uv venv --python 3.12 .venv` then
  `uv pip install -r requirements-dev.txt -r requirements-ocr.txt greenlet`.
- On Windows the venv layout differs (`.venv\Scripts\python.exe`).
- Model downloads: PaddleOCR fetches PP-OCR models on first run
  (`PADDLE_PDX_CACHE_HOME` overrides the cache dir).

---

## 6. Recommended next phase (exact starting point)

> Status: **RELEASE PASS COMPLETE (2026-09-09) — repository is publish-ready.**
> No 501 endpoints. Release smoke test `scripts/release_smoke_test.py`
> (22 API checks across the three demo journeys incl. immutability-409)
> passes against a freshly seeded DB. README has a verified no-Docker
> quickstart (Option B2) and OCR setup. Only remaining step: `git init` +
> push (see checkpoint "NEXT STEPS").

Optional, strictly post-release:
1. Analytics dashboard (spec §49), demo reset button, kiosk
   auto-return timeout (spec §47).
2. Real STT/TTS vendor behind `SpeechProvider`; Gemini-keyed
   summary behind the existing LLM seam (deterministic draft stays fallback).
3. Offline queue (spec §30) if time permits.
