"""Business logic services.

Boundaries (mirror the product pipeline in docs/PROTOTYPE_BUILD_SPEC.md §33):

- dialogue  — interview state machine, question planner, LLM extraction
- speech    — speech provider orchestration
- ocr       — image preprocessing + OCR orchestration
- documents — upload, classification, extraction, timeline
- summary   — physician-ready summary drafting
- triage    — deterministic red-flag rules
- fhir      — canonical case -> FHIR mapping + export

Each service depends on provider interfaces from ``app.integrations``, never
on vendor SDKs directly. Phase 1 ships only the boundaries.
"""
