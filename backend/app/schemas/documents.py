"""Document schemas (Phase 4 upload core + Phase 4/2 OCR/extraction)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentRead(BaseModel):
    document_id: uuid.UUID
    session_id: uuid.UUID
    file_name: str
    mime_type: str | None = None
    sha256: str | None = None
    document_type: str | None = None  # classified during reprocess (spec §16.3)
    processing_status: str  # uploaded | processing | completed | failed
    uploaded_at: datetime
    extraction: dict | None = None  # structured OCR/extraction payload (Phase 4/2)
    page_count: int | None = None
    ocr_provider: str | None = None
    ocr_mocked: bool | None = None
    processed_at: datetime | None = None
    last_error: str | None = None


class DocumentReprocessResponse(BaseModel):
    """Result of POST /documents/{id}/reprocess."""

    document_id: uuid.UUID
    session_id: uuid.UUID
    status: str = Field(description="processing_status after the run: completed | failed")
    document_type: str | None = None
    page_count: int | None = None
    ocr_provider: str | None = None
    ocr_mocked: bool | None = Field(
        default=None,
        description="true = simulated OCR fixture, NOT real OCR of the uploaded file",
    )
    confidence: float | None = None
    extraction: dict | None = None
    processed_at: datetime | None = None
    error: str | None = None
    message: str
