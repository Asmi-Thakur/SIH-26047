# MediKiosk 🏥 🗣️

> **AI-powered digital clinical intake for Indian hospitals** — voice + touch history-taking, medical document digitization, and physician-ready case summaries.
> Built for **Smart India Hackathon 2026 — Problem Statement 26047 (Patient Case-Taking Software, Ministry of Ayush).**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![React](https://img.shields.io/badge/React-19-blue)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-7-646CFF)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-4-38B2AC)](https://tailwindcss.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://www.docker.com/)
[![SIH 2026](https://img.shields.io/badge/SIH%202026-PS%2026047-orange)](https://sih.gov.in/)

---

## 📋 Table of Contents

1. [Overview](#-overview)
2. [Key Features](#-key-features)
3. [Architecture & Pipeline](#-architecture--pipeline)
4. [Tech Stack](#-tech-stack)
5. [Repository Layout](#-repository-layout)
6. [Getting Started](#-getting-started)
7. [Demo Mode](#-demo-mode)
8. [Roadmap](#-roadmap)
9. [License & Disclaimer](#-license--disclaimer)

---

## 🚀 Overview

**MediKiosk** is an AI-assisted clinical intake platform that lets a patient record their complete medical history — through **natural spoken conversation** or **guided touchscreen interaction** — *before* they enter the consultation room. It also digitizes their existing paper documents (prescriptions, lab reports, discharge summaries) and assembles everything into a **structured, physician-ready clinical summary** that plugs into the hospital system and the ABDM/FHIR ecosystem.

**The problem:** Indian government OPDs see 4,000–10,000 patients per day with just 2–5 minutes per consultation. History-taking — the most diagnostic activity (70–80% of diagnoses before investigation) — is systematically under-elicited. AYUSH institutions face an even deeper burden: Ayurvedic history-taking (Trividha, Ashtavidha, Dashavidha Pariksha) demands assessment of Prakriti, Vikriti, Agni, Koshtha, Ahara-Vihara, Nidana, and Samprapti — practically impossible to capture manually in OPD time.

**The solution:** a self-service kiosk/app that offloads structured history acquisition from overburdened clinical staff — like ATMs did for banking — and solves the "first-mile" problem of getting structured clinical data into the ABDM ecosystem before the encounter.

> ⚠️ **AI assists, it does not diagnose.** MediKiosk produces a *draft* history for physician review. The doctor edits, accepts, or rejects every element. The system never presents an AI-generated diagnosis as a confirmed one, and emergency escalation is driven by deterministic rules.

---

## ✨ Key Features

| Feature | Description |
| :--- | :--- |
| 🗣️ **Multilingual Voice Interview** | Indian-language ASR + TTS (Hindi, English, + regional languages) |
| 👆 **Guided Touch Interview** | Icon-driven, large-target UI for low-literacy and elderly users |
| 🧠 **Adaptive Clinical Questioning** | SOCRATES-style follow-ups driven by a controlled question bank |
| 🪔 **AYUSH Mode** | Dashavidha Pariksha + Ahara-Vihara sections for AYUSH OPDs |
| 🚨 **Red-Flag Triage Engine** | Deterministic safety rules → urgent priority alerts (no AI diagnosis) |
| 📄 **Medical Document Digitization** | OCR for printed + handwritten, multilingual documents |
| 🗂️ **Timeline & Abnormal-Value Flagging** | Chronological document sort; lab values checked against own reference ranges |
| 📋 **Physician-Ready Summary** | Structured case draft with source provenance, editable section by section |
| 🔐 **Consent-First Privacy** | Explicit, revocable consent; temporary session data wiped after submission |
| 🏥 **ABDM / FHIR Interoperability** | FHIR R4 export via a `HealthRecordAdapter` boundary (mock → HAPI → ABDM sandbox) |
| 🎛️ **Demo Mode** | Deterministic sample transcripts/OCR/LLM output — judging demos need no API keys |

---

## 🏗️ Architecture & Pipeline

```
PATIENT ARRIVES
      │
      ▼
IDENTITY + LANGUAGE + CONSENT
      │
      ▼
VOICE / TOUCH CLINICAL INTERVIEW ──► RED-FLAG ENGINE ──► TRIAGE ALERT
      │
      ▼
UPLOAD / SCAN PRIOR DOCUMENTS
      │
      ▼
OCR + CLASSIFICATION + ENTITY EXTRACTION
      │
      ▼
TIMELINE + ABNORMAL-VALUE HIGHLIGHTS
      │
      ▼
AI STRUCTURED CASE SUMMARY
      │
      ▼
DOCTOR REVIEW / EDIT / CONFIRM
      │
      ▼
FHIR BUNDLE → HAPI FHIR / ABDM
      │
      ▼
END SESSION + CLEAR TEMPORARY DATA
```

Architecture principle: **build the deterministic shell first and add AI inside
it.** The system stays functional when the LLM, speech, OCR, or FHIR are
unavailable. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for details.

---

## 🛠️ Tech Stack

| Component | Technology |
| :--- | :--- |
| **Frontend** | React 19 · Vite · TypeScript · Tailwind CSS 4 · React Router · TanStack Query · Lucide React |
| **Backend** | Python · FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · Alembic |
| **Database** | PostgreSQL 16 |
| **Speech** | Mock STT/TTS implemented; Sarvam AI / AI4Bharat IndicConformer planned — behind the `SpeechProvider` protocol |
| **LLM** | Deterministic extractor implemented; Gemini (structured output) key-gated — behind the `LLMProvider` protocol |
| **OCR** | PaddleOCR primary (verified on py3.10–3.12); honest simulated provider as fallback — behind the `OCRProvider` protocol |
| **Interop** | Local FHIR R4 Bundle export implemented; HAPI/ABDM push behind `HealthRecordAdapter` — no live ABDM connectivity is claimed |
| **Infrastructure** | Docker Compose |

---

## 📁 Repository Layout

```text
medikiosk/
├── README.md · CLAUDE.md · ARCHITECTURE.md
├── docker-compose.yml · .env.example · .gitignore · LICENSE
├── docs/
│   ├── PROTOTYPE_BUILD_SPEC.md   # product + implementation source of truth
│   ├── PROJECT_CHECKPOINT.md     # canonical handoff: current state + test results
│   ├── AI_HANDOFF.md             # architecture map for continuing development
│   ├── API_CONTRACT.md           # REST endpoints (implemented)
│   ├── DATA_MODEL.md             # canonical clinical case model + DB schema
│   └── DECISIONS.md              # architecture decision log (ADR-001…021)
├── frontend/                     # React kiosk + doctor console (Vite/TS/Tailwind)
├── backend/                      # FastAPI + async SQLAlchemy + Alembic
│   └── requirements-ocr.txt      # optional real-OCR engine (PaddleOCR, py3.10–3.12)
├── scripts/
│   ├── seed_demo_data.py         # repeatable synthetic demo seed (3 cases)
│   ├── release_smoke_test.py     # end-to-end API smoke test
│   └── daemonize.py              # detached dev-server launcher (macOS/Linux)
└── storage/                      # uploaded documents at runtime (gitignored)
```

---

## 🚀 Getting Started

### Prerequisites

* Node.js 18+
* Python 3.11 or 3.12 (3.12 verified; real PaddleOCR requires 3.10–3.12 — see [OCR setup](#-demo-mode))
* PostgreSQL 16 via Docker — *or nothing at all*: the backend also runs on a local SQLite file for demos (Option B2)

### Option A — Everything in Docker

```bash
git clone <your-repository-url>
cd medikiosk

cp .env.example .env
docker compose up --build
```

Then open:

* Frontend → http://localhost:5173
* Backend API docs (Swagger) → http://localhost:8000/docs

### Option B — Local development

```bash
# 1. Infrastructure (PostgreSQL)
docker compose up -d postgres

# 2. Backend
cd backend
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
# point DATABASE_URL at localhost:5432, then:
alembic upgrade head
uvicorn app.main:app --reload        # http://localhost:8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

### Option B2 — Zero-infrastructure demo (SQLite, no Docker)

The verified quickstart — one venv, one SQLite file, no external services:

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# 1. Schema (or skip: the seed script creates tables itself)
DATABASE_URL="sqlite+aiosqlite:///./dev.db" .venv/bin/python -m alembic upgrade head

# 2. Seed the 3 synthetic demo cases (idempotent — safe to re-run)
cd ..
DATABASE_URL="sqlite+aiosqlite:///./backend/dev.db" backend/.venv/bin/python scripts/seed_demo_data.py

# 3. Run
cd backend && DATABASE_URL="sqlite+aiosqlite:///./dev.db" .venv/bin/python -m uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev
```

### Release smoke test (API level)

With the backend running against a freshly seeded database:

```bash
backend/.venv/bin/python scripts/release_smoke_test.py --base http://127.0.0.1:8000
```

It walks all three demo journeys through the real API — urgent triage →
confirm → FHIR export → immutability (409 on edit-after-confirm), routine
case with `document_extracted` provenance and abnormal-value flag, AYUSH
`canonical.ayush` block — and exits non-zero on any failure.

### Smoke check

```bash
curl http://localhost:8000/api/health
# {"status":"ok","service":"medikiosk-backend","environment":"development","database":"ok"}
```

---

## 🎛️ Demo Mode

Set `DEMO_MODE=true` (default in `.env.example`) and the backend uses
deterministic providers where real ones are unavailable, so the project runs
with no paid external API:

```text
LLM        → deterministic extractor        (mocked: true)
Speech     → MockSpeechProvider             (mocked: true)
OCR        → real PaddleOCR when installed  (requirements-ocr.txt, py3.12 venv);
             otherwise the simulated provider, always labelled "mocked: true"
FHIR       → real local R4 Bundle writer    (ABDM push = future adapter)
```

Judges can run the full flow repeatedly and receive consistent output. Seed
the three scripted demo cases (urgent / routine+lab / AYUSH) with:

```bash
# from the repository root (creates tables if needed; safe to re-run)
DATABASE_URL="sqlite+aiosqlite:///./backend/dev.db" backend/.venv/bin/python scripts/seed_demo_data.py
```

Then verify the whole pipeline headlessly with `scripts/release_smoke_test.py`
(see [Release smoke test](#release-smoke-test-api-level)).

### OCR setup (real engine, optional)

`OCR_PROVIDER=auto` (default) uses **real PaddleOCR when importable** and
otherwise falls back to the honest simulated provider (always labelled
`mocked: true` — UI shows "Simulated OCR"). To enable the real engine:

```bash
cd backend
.venv/bin/pip install -r requirements-ocr.txt   # paddlepaddle + paddleocr + pypdfium2
```

Requires Python 3.10–3.12 (PaddlePaddle publishes no wheels for 3.13/3.14).
Verified combination: CPython 3.12 + paddlepaddle 3.3.1 + paddleocr 3.7.0 on
macOS ARM64 — a synthetic printed lab report OCRs at ≈0.99 confidence and its
abnormal glucose value flows into the case with `document_extracted`
provenance. Models download to `~/.paddlex/` on first use; `OCR_PROVIDER=mock`
forces the labelled simulation, `OCR_PROVIDER=paddleocr` requires the real
engine (raises if missing).

---

## 🗺️ Roadmap

**Phase 1 — Foundation ✅**
- [x] Monorepo, Docker Compose, PostgreSQL, environment config
- [x] FastAPI skeleton: config, async SQLAlchemy, Alembic, health endpoints, CORS
- [x] 12 foundational DB tables + initial Alembic migration
- [x] React + Vite + TS + Tailwind shell with patient/doctor route skeleton
- [x] API client, canonical TypeScript types, API contract docs

**Phase 2 — Touch intake ✅** · Welcome/identity/consent screens, question bank, state machine
**Phase 3 — Triage ✅** · deterministic red-flag rules
**Phase 4 — Voice ✅ (mock STT/TTS)** · MediaRecorder + provider seam; real ASR/TTS vendors pending
**Phase 5 — Documents ✅** · upload, real PaddleOCR (py3.12) + labelled mock fallback, classification, extraction, abnormal-value flags, document→case provenance
**Phase 6 — Summary ✅** · synthesis, provenance, physician editor, two-step confirm
**Phase 7 — FHIR ✅** · confirmed case → provenance-labelled FHIR R4 Bundle (local; ABDM push = adapter boundary)
**Phase 8 — AYUSH ✅** · Dashavidha Pariksha + Ahara-Vihara structured section (department-gated)
**Phase 9 — Offline** · local queue + recovery (future)
**Phase 10 — Judging polish ✅** · seeded demo cases (`scripts/seed_demo_data.py`), real patient Documents/Review screens, honest mock labelling

See `docs/PROTOTYPE_BUILD_SPEC.md` §50 for the detailed milestone definitions.

---

## 📄 License & Disclaimer

Distributed under the **MIT License**. See `LICENSE`.

> ⚠️ **Prototype only.** Built for Smart India Hackathon 2026 using synthetic/demo data. Not a validated medical device, does not replace clinical judgment, and must not be deployed for real patient care without clinical validation, institutional governance, security/privacy review, and regulatory compliance.
