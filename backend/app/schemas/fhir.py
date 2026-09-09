"""FHIR export schemas (Phase 7).

The bundle itself is stored and returned as a raw JSON dict — the canonical
FHIR resource shapes are validated by the mapper's tests, not re-modelled in
Pydantic. These schemas describe the *wire* envelope for the two endpoints.
Mirrored in frontend/src/types/index.ts and docs/API_CONTRACT.md.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FhirExportResponse(BaseModel):
    """Result of POST /fhir/export/{case_id} (one attempt)."""

    export_id: uuid.UUID
    case_id: uuid.UUID
    session_id: uuid.UUID
    status: str  # pending | succeeded | failed
    destination: str | None = None
    error: str | None = None
    attempted_at: datetime | None = None
    succeeded_at: datetime | None = None
    created_at: datetime
    bundle: dict | None = Field(
        default=None,
        description="FHIR R4 Bundle (resourceType=Bundle, type=collection) on success.",
    )
    message: str


class FhirExportStatusResponse(BaseModel):
    """GET /fhir/export/{case_id} — last attempt for the case (null if never)."""

    case_id: uuid.UUID
    session_id: uuid.UUID
    export: FhirExportResponse | None = None
