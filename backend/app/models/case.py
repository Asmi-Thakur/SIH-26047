"""Case models: the physician-facing summary record and its immutable versions."""
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONB, utcnow


class CaseSummary(Base):
    """Current case summary for a session (one per session)."""

    __tablename__ = "case_summaries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id"), unique=True
    )
    # draft -> physician_edited -> confirmed (docs/DATA_MODEL.md §2)
    status: Mapped[str] = mapped_column(
        String(24), default="draft", server_default=text("'draft'")
    )
    content: Mapped[dict | None] = mapped_column(JSONB)
    draft_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default=text("1")
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column()
    confirmed_at: Mapped[datetime | None] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, onupdate=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )


class CaseVersion(Base):
    """Immutable snapshot of the case content at a point in time."""

    __tablename__ = "case_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    case_summary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_summaries.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(24), default="draft", server_default=text("'draft'")
    )
    content: Mapped[dict] = mapped_column(JSONB)
    edited_by: Mapped[uuid.UUID | None] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=text("CURRENT_TIMESTAMP")
    )

    __table_args__ = (
        UniqueConstraint(
            "case_summary_id",
            "version_number",
            name="uq_case_versions_case_summary_id_version_number",
        ),
    )
