"""Platform models: staff users, audit trail, FHIR exports, sync queue."""
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONB, utcnow


class User(Base):
    """Staff user (doctor / triage / admin)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(
        String(16), default="doctor", server_default=text("'doctor'")
    )
    display_name: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, onupdate=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )


class AuditLog(Base):
    """Append-only audit trail for sensitive actions."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_type: Mapped[str] = mapped_column(String(16))  # patient | doctor | system | admin
    actor_id: Mapped[uuid.UUID | None] = mapped_column()
    action: Mapped[str] = mapped_column(String(64), index=True)  # e.g. CONSENT_GRANTED
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    details: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )


class FhirExport(Base):
    """A FHIR export attempt for a session's confirmed case."""

    __tablename__ = "fhir_exports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default=text("'pending'")
    )  # pending | succeeded | failed
    bundle: Mapped[dict | None] = mapped_column(JSONB)
    destination: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)

    attempted_at: Mapped[datetime | None] = mapped_column()
    succeeded_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )


class SyncQueue(Base):
    """Offline sync queue item (browser/edge retries; Phase 9+)."""

    __tablename__ = "sync_queue"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sessions.id"))
    operation: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default=text("'pending'")
    )

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, onupdate=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
