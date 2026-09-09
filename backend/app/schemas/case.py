"""Case endpoint schemas (Phase 6 — unified case + physician review).

``case_id`` on the wire is the ``case_summaries.id`` UUID. The canonical case
content follows docs/DATA_MODEL.md §1; ``CaseRead.canonical`` is the freshly
assembled machine-readable case and ``CaseRead.summary`` is the physician-
ready (editable) text draft. Mirrored in frontend/src/types/index.ts.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CaseListItem(BaseModel):
    """One row of the physician case list (GET /cases)."""

    session_id: uuid.UUID
    case_id: uuid.UUID | None = None  # None until a summary row exists
    token: str | None = None
    patient_name: str | None = None
    age: int | None = None
    language: str | None = None
    department: str | None = None
    state: str
    consent_granted: bool | None = None
    chief_complaint: str | None = None
    status: str | None = None  # draft | physician_edited | confirmed (None = no case yet)
    has_documents: bool = False
    urgent_alerts: int = 0
    started_at: datetime
    completed_at: datetime | None = None
    confirmed_at: datetime | None = None


class CaseListResponse(BaseModel):
    count: int
    items: list[CaseListItem]


class CaseRead(BaseModel):
    """Full case for the physician console.

    ``canonical`` is the current assembled case (patient-reported source of
    truth); ``summary`` is the physician-ready text draft the doctor edits.
    """

    case_id: uuid.UUID
    session_id: uuid.UUID
    status: str  # draft | physician_edited | confirmed
    draft_version: int
    canonical: dict
    summary: dict[str, str]
    updated_at: datetime
    confirmed_at: datetime | None = None


class SummaryPatch(BaseModel):
    """Physician edits to the summary text sections."""

    summary: dict[str, str]
    note: str | None = Field(default=None, max_length=500)


class CaseActionResponse(BaseModel):
    case_id: uuid.UUID
    session_id: uuid.UUID
    status: str
    draft_version: int
    confirmed_at: datetime | None = None
    message: str