"""Document intake service (Phase 4 upload core).

Uploads are validated (type + size), hashed, and the ORIGINAL file is
retained on disk so every later extraction step can be traced back to its
source (spec §16/§31). OCR is NOT invoked here — processing_status stays
``uploaded`` until the PaddleOCR milestone.
"""
import hashlib
import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.clinical import Document
from app.services.sessions import get_session as require_session

ALLOWED_TYPES: dict[str, tuple[str, ...]] = {
    "image": ("image/jpeg", "image/png", "image/webp"),
    "pdf": ("application/pdf",),
}
ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".pdf")


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"status": "error", "code": code, "message": message},
    )


def validate_file(file_name: str, mime_type: str | None, size: int, settings: Settings) -> None:
    lowered = file_name.lower()
    if not lowered.endswith(ALLOWED_EXTENSIONS):
        raise _error(
            415,
            "unsupported_media_type",
            f"Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    if mime_type and mime_type not in {t for types in ALLOWED_TYPES.values() for t in types}:
        raise _error(415, "unsupported_media_type", f"Unsupported MIME type: {mime_type}")
    if size > settings.max_upload_bytes:
        raise _error(
            413,
            "payload_too_large",
            f"File exceeds the {settings.max_upload_mb} MB limit",
        )


async def create_document(
    db: AsyncSession,
    session_id: uuid.UUID,
    file_name: str,
    mime_type: str | None,
    content: bytes,
    settings: Settings,
) -> Document:
    """Persist a validated upload and retain the original bytes on disk."""
    await require_session(db, session_id)  # 404 session_not_found
    validate_file(file_name, mime_type, len(content), settings)

    sha256 = hashlib.sha256(content).hexdigest()
    storage_root = Path(settings.upload_dir)
    storage_root.mkdir(parents=True, exist_ok=True)
    document_id = uuid.uuid4()
    relative = Path(f"{session_id}") / f"{document_id}{Path(file_name).suffix.lower()}"
    absolute = storage_root / relative
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_bytes(content)  # original retained for source tracing

    row = Document(
        id=document_id,
        session_id=session_id,
        file_name=file_name,
        mime_type=mime_type,
        sha256=sha256,
        storage_path=str(relative),
        processing_status="uploaded",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row
