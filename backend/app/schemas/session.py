"""Session schemas.

Used by the sessions router (implemented in Phase 2) and mirrored in
``frontend/src/types/index.ts`` so the contract stays pinned — see
docs/API_CONTRACT.md. Pydantic models are authoritative for the backend.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    token: str | None = Field(default=None, max_length=64)
    language: str = Field(default="en", max_length=8)
    department: str | None = Field(default=None, max_length=64)
    demo: bool = False


class SessionRead(BaseModel):
    """Current state of a patient session.

    ``session_id`` is the wire identifier (the ORM column is ``id``).
    ``case_id`` stays null until the summary milestone creates a case.
    """

    session_id: uuid.UUID
    patient_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None
    state: str
    mode: str | None = None
    department: str | None = None
    is_demo: bool = False
    started_at: datetime
    completed_at: datetime | None = None


class SessionListItem(BaseModel):
    """One row of the physician queue (GET /sessions)."""

    session_id: uuid.UUID
    token: str | None = None
    patient_name: str | None = None
    age: int | None = None
    language: str | None = None
    department: str | None = None
    state: str
    consent_granted: bool | None = None  # None = decision not recorded yet
    chief_complaint: str | None = None
    is_demo: bool = False
    started_at: datetime
    completed_at: datetime | None = None


class SessionListResponse(BaseModel):
    count: int
    items: list[SessionListItem]


class ConsentCreate(BaseModel):
    granted: bool
    purposes: list[str] | None = Field(default=None, max_length=8)
    consent_text_version: str | None = Field(default=None, max_length=32)


class ConsentRead(BaseModel):
    session_id: uuid.UUID
    granted: bool
    purposes: list[str] | None = None
    consent_text_version: str | None = None
    created_at: datetime
    revoked_at: datetime | None = None
