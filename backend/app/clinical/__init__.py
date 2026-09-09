"""Clinical domain content and schemas.

Subpackages (populated in Phase 2+):

- questions   — version-controlled question bank (YAML/JSON)
- rules       — deterministic red-flag rules
- schemas     — canonical clinical extraction schemas (Pydantic)
- terminology — symptom/drug/allergy normalization dictionaries

Content lives here, NOT inside UI or router code, so clinical workflows can be
edited without touching the frontend (docs/DECISIONS.md ADR-010).
"""
