"""Clinical capture models: answers, uploaded documents, triage alerts."""
import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONB, utcnow


class Answer(Base):
    """A single patient answer (touch choice or voice transcript)."""

    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"))
    question_id: Mapped[str] = mapped_column(String(64))
    input_mode: Mapped[str | None] = mapped_column(String(16))  # voice | touch | manual
    raw_answer: Mapped[str | None] = mapped_column(Text)
    structured_value: Mapped[dict | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(32))

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )

    __table_args__ = (
        Index("ix_answers_session_id_question_id", "session_id", "question_id"),
    )


class Document(Base):
    """An uploaded medical document (prescription, lab report, …)."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), index=True
    )
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(64))
    sha256: Mapped[str | None] = mapped_column(String(64))
    document_type: Mapped[str | None] = mapped_column(String(32))
    storage_path: Mapped[str | None] = mapped_column(String(512))
    processing_status: Mapped[str] = mapped_column(
        String(16), default="uploaded", server_default=text("'uploaded'")
    )
    # --- Phase 4/2: OCR/extraction results (all nullable until processed) ---
    extraction: Mapped[dict | None] = mapped_column(JSONB)
    page_count: Mapped[int | None] = mapped_column()
    ocr_provider: Mapped[str | None] = mapped_column(String(32))
    ocr_mocked: Mapped[bool | None] = mapped_column()
    processed_at: Mapped[datetime | None] = mapped_column()
    last_error: Mapped[str | None] = mapped_column(Text)

    uploaded_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )


class TriageAlert(Base):
    """Red-flag alert raised by the deterministic rule engine (Phase 3+)."""

    __tablename__ = "triage_alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), index=True
    )
    priority: Mapped[str] = mapped_column(String(16))  # routine | urgent
    rules_triggered: Mapped[list | None] = mapped_column(JSONB)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), default="active", server_default=text("'active'")
    )

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column()
