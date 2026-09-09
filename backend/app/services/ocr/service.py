"""Document OCR/extraction orchestration (Phase 4/2).

Drives the document lifecycle behind ``POST /documents/{id}/reprocess``:

    uploaded | failed | completed ──reprocess──> processing ──> completed | failed

Steps: load the retained original (spec §16/§17 — the physician can always
inspect the source), run OCR through the OCRProvider registry (mock default,
real PaddleOCR when available), classify the document (spec §16.3) and run
the deterministic clinical extractor, then persist everything on the
documents row. Any failure lands the row on ``failed`` with ``last_error``
set — an OCR failure never corrupts the document or the case (spec §45).

Consent rule (spec P03): document processing requires a GRANTED consent for
the session — declined-or-never-consented sessions are refused with 409
``consent_required``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import utcnow
from app.models.clinical import Document
from app.models.intake import Consent, PatientSession
from app.models.platform import AuditLog
from app.services.ocr.extract import TYPE_LABELS, classify_document, extract_document_facts
from app.services.ocr.registry import get_ocr_provider


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"status": "error", "code": code, "message": message},
    )


def _state_transition_ok(current: str) -> bool:
    """Reprocess is allowed from uploaded / completed / failed — never mid-flight."""
    return current in {"uploaded", "completed", "failed"}


def build_extraction_payload(
    *,
    provider_name: str,
    mocked: bool,
    confidence: float | None,
    page_count: int,
    pages: list[dict],
    text: str,
    document_type: str,
    facts: dict,
) -> dict:
    """Assemble the persisted extraction payload (honestly labelled)."""
    return {
        "provider": provider_name,
        "mocked": mocked,
        "confidence": confidence,
        "page_count": page_count,
        "pages": pages,
        "text": text,
        "document_type": document_type,
        "document_type_label": TYPE_LABELS.get(document_type, document_type),
        "classification_method": "keyword_v1",
        "tests": facts.get("tests", []),
        "abnormal_values": facts.get("abnormal_values", []),
        "medications": facts.get("medications", []),
        "conditions": facts.get("conditions", []),
        "engine_note": (
            "Deterministic mock fixture — NOT real OCR of the uploaded file."
            if mocked
            else "Real PaddleOCR output of the retained original."
        ),
    }


async def reprocess_document(db: AsyncSession, document_id: uuid.UUID) -> Document:
    """Run OCR + extraction for one document, updating its lifecycle.

    Raises structured HTTPExceptions for unknown documents and missing
    consent; processing failures are persisted on the row (status ``failed``,
    ``last_error`` set) and re-raised as a structured 502 so the API response
    is machine-readable.
    """
    row = await db.get(Document, document_id)
    if row is None:
        raise _error(404, "document_not_found", f"No document found for {document_id}")

    session = await db.get(PatientSession, row.session_id)
    if session is None:
        raise _error(404, "session_not_found", "The document's session no longer exists")

    consent = (
        await db.execute(select(Consent).where(Consent.session_id == row.session_id))
    ).scalar_one_or_none()
    if consent is None or not consent.granted:
        raise _error(
            409,
            "consent_required",
            "Document processing requires granted consent (spec P03).",
        )

    if not _state_transition_ok(row.processing_status):
        raise _error(
            409,
            "document_already_processing",
            f"Document is already {row.processing_status}; retry later.",
        )

    settings = get_settings()
    storage_path = (settings.upload_dir and row.storage_path) and (
        f"{settings.upload_dir.rstrip('/')}/{row.storage_path}"
    )
    if not storage_path:
        raise _error(409, "document_source_missing", "The original file is not retained on disk.")

    # 1) claim the row synchronously (visible transition: uploaded -> processing)
    row.processing_status = "processing"
    await db.commit()
    await db.refresh(row)

    try:
        content = await _read_original(storage_path)
        provider, mocked = get_ocr_provider()
        ocr = await provider.extract(content, mime_type=row.mime_type)

        document_type = classify_document(ocr.get("text") or "")
        facts = extract_document_facts(ocr.get("text") or "")

        pages = ocr.get("pages") or []
        row.extraction = build_extraction_payload(
            provider_name=str(ocr.get("provider") or provider.name),
            mocked=bool(ocr.get("mocked", mocked)),
            confidence=ocr.get("confidence"),
            page_count=int(ocr.get("page_count") or len(pages)),
            pages=pages,
            text=str(ocr.get("text") or ""),
            document_type=document_type,
            facts=facts,
        )
        row.document_type = document_type
        row.page_count = int(ocr.get("page_count") or len(pages))
        row.ocr_provider = str(ocr.get("provider") or provider.name)
        row.ocr_mocked = bool(ocr.get("mocked", mocked))
        row.processing_status = "completed"
        row.processed_at = utcnow()
        row.last_error = None
    except HTTPException:
        row.processing_status = "failed"
        row.processed_at = utcnow()
        row.last_error = "OCR processing failed"
        await db.commit()
        await db.refresh(row)
        raise
    except Exception as exc:  # noqa: BLE001 — persisted, never a bare 500
        row.processing_status = "failed"
        row.processed_at = utcnow()
        row.last_error = str(exc)[:2000]
        await db.commit()
        await db.refresh(row)
        raise _error(
            502,
            "ocr_failed",
            "OCR processing failed; the document is marked failed and can be retried.",
        ) from exc

    db.add(
        AuditLog(
            actor_type="system",
            action="OCR_COMPLETED",
            entity_type="document",
            entity_id=row.id,
            details={
                "session_id": str(row.session_id),
                "provider": row.ocr_provider,
                "mocked": row.ocr_mocked,
                "document_type": row.document_type,
                "page_count": row.page_count,
                "abnormal_flags": len(row.extraction.get("abnormal_values") or [])
                if row.extraction
                else 0,
            },
        )
    )
    await db.commit()
    await db.refresh(row)
    return row


async def _read_original(storage_path: str) -> bytes:
    from pathlib import Path

    path = Path(storage_path)
    if not path.exists():
        raise FileNotFoundError(f"Original file missing: {storage_path}")
    return path.read_bytes()
