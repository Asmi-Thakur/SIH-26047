"""Intake models: patient sessions and consent decisions."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONB, utcnow


class PatientSession(Base):
    """One patient intake journey (table: ``sessions``)."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patients.id"), index=True
    )
    # Progress state of the interview state machine (see docs/DATA_MODEL.md §2).
    state: Mapped[str] = mapped_column(
        String(32), default="welcome", server_default=text("'welcome'")
    )
    mode: Mapped[str | None] = mapped_column(String(16))  # speak | touch | speak_touch
    department: Mapped[str | None] = mapped_column(String(64))

    started_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    completed_at: Mapped[datetime | None] = mapped_column()
    is_demo: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )


class Consent(Base):
    """Explicit consent decision for a session (one per session)."""

    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), unique=True
    )
    granted: Mapped[bool] = mapped_column(Boolean)
    purposes: Mapped[list | None] = mapped_column(JSONB)
    consent_text_version: Mapped[str | None] = mapped_column(String(32))

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    revoked_at: Mapped[datetime | None] = mapped_column()
