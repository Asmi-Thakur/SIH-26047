# CLAUDE.md — Guidance for AI coding agents working on MediKiosk

This file gives future AI agents (Claude, Cursor, Kimi, Codebuff, etc.) the
context needed to extend this repository safely and consistently.

## Project goal

**MediKiosk** is an AI-assisted patient clinical intake platform built for
**Smart India Hackathon 2026 — Problem Statement 26047 (Patient Case-Taking
Software, Ministry of Ayush / All India Institute of Ayurveda)**.

A patient uses a kiosk/tablet *before* the consultation to:

1. give consent,
2. record a clinical history by **voice or touch**,
3. upload prior paper documents (prescriptions, lab reports, discharge summaries),
4. receive automatic **red-flag triage** for urgent symptoms,
5. let the system assemble a **physician-ready case summary**.

The physician then reviews/edits/confirms the draft, and the confirmed case is
exported as a FHIR R4 bundle.

## Core rule

**AI assists the workflow but does not diagnose.**

MediKiosk is *not* autonomous diagnostic software. The physician is the final
decision-maker. Never present an AI-generated statement as a confirmed
diagnosis; emergency escalation must be driven by **deterministic rules**, not
by the LLM.

## Source of truth

The product/implementation specification is:

```
docs/PROTOTYPE_BUILD_SPEC.md
```

**Read it before making major changes.** It is the source of truth for product
requirements and must not be replaced by ad-hoc architecture. Architectural
decisions are tracked in `docs/DECISIONS.md` — update that log instead of
silently changing decisions.

## Engineering rules

- Read `docs/PROTOTYPE_BUILD_SPEC.md` before major changes.
- Preserve the existing architecture (see `ARCHITECTURE.md`).
- Never put API keys or secrets in the frontend. Secrets live only in backend
  environment variables (`.env`, which is git-ignored).
- Do not silently change API contracts. If a contract must change, update
  `docs/API_CONTRACT.md` and the affected TypeScript/Pydantic types together.
- Use typed schemas: Pydantic on the backend, TypeScript types on the frontend.
- Write tests for business logic (`pytest` backend, `vitest` frontend).
- Keep provider integrations (LLM, speech, OCR, FHIR/ABDM) behind interfaces —
  never hard-code a vendor SDK call across the codebase.
- Do not introduce autonomous diagnosis.
- Do not bypass physician confirmation before export.
- Never use or commit production/real patient data — synthetic demo data only.
- Prefer small, composable services over large modules.
- Do not create giant generic `utils.py` files.
- Provider mock implementations must be the default for local dev (`DEMO_MODE=true`).

## Repository map

```text
frontend/   React + Vite + TypeScript + Tailwind kiosk/doctor UI
backend/    FastAPI + async SQLAlchemy + Alembic + PostgreSQL
clinical/   question bank, rules and terminology (future phases)
demo/       synthetic demo fixtures (future phases)
scripts/    dev/seed/reset scripts (future phases)
docs/       PROTOTYPE_BUILD_SPEC.md, API_CONTRACT.md, DATA_MODEL.md, DECISIONS.md
```

## Workflow for future agents

1. Inspect the repository (git status, tree) before changing anything.
2. Read the relevant parts of `docs/PROTOTYPE_BUILD_SPEC.md`.
3. Inspect the existing implementation for the area you are touching.
4. Identify which contracts (API, DB, types, docs) are affected.
5. Implement the smallest coherent change.
6. Run tests: `pytest` (backend), `npm test` (frontend).
7. Run build/type checks: `tsc -b && vite build` (frontend), `python -m compileall app` or similar (backend).
8. Update the documentation that describes what you changed.
9. Summarize the files you changed and the commands you ran.

## Status

Phase 1 (foundation: infra, backend skeleton, frontend shell, contracts) is
implemented. Later phases (interview engine, triage rules, voice, OCR, summary,
FHIR) are stubbed behind 501 placeholders and interface boundaries — implement
them in dependency order, per `docs/PROTOTYPE_BUILD_SPEC.md` §50.
