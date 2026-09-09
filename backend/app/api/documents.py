"""Document endpoints — Phase 4 upload core + Phase 4/2 OCR/reprocess.

POST /documents/upload          : validated multipart upload, original retained
                                  on disk, row status ``uploaded``.
GET  /documents/{id}            : metadata + processing status + extraction.
POST /documents/{id}/reprocess  : run OCR/extraction now (lifecycle
                                  uploaded|completed|failed -> processing ->
                                  completed|failed; consent-gated; honestly
                                  labelled mock vs real provider).
"""
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api.deps import AppSettings, DbSession
from app.models.clinical import Document
from app.schemas.documents import DocumentRead, DocumentReprocessResponse
from app.services.documents.store import create_document
from app.services.ocr.service import reprocess_document

router = APIRouter(prefix="/documents", tags=["documents"])


def _document_read(row: Document) -> DocumentRead:
    return DocumentRead(
        document_id=row.id,
        session_id=row.session_id,
        file_name=row.file_name,
        mime_type=row.mime_type,
        sha256=row.sha256,
        document_type=row.document_type,
        processing_status=row.processing_status,
        uploaded_at=row.uploaded_at,
        extraction=row.extraction,
        page_count=row.page_count,
        ocr_provider=row.ocr_provider,
        ocr_mocked=row.ocr_mocked,
        processed_at=row.processed_at,
        last_error=row.last_error,
    )


@router.post(
    "/upload",
    status_code=201,
    response_model=DocumentRead,
    summary="Upload a medical document (image or PDF)",
)
async def upload_document(
    db: DbSession,
    settings: AppSettings,
    session_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
) -> DocumentRead:
    content = await file.read()
    row = await create_document(
        db, session_id, file.filename or "upload", file.content_type, content, settings
    )
    return _document_read(row)


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Document metadata + processing status + extraction",
)
async def get_document(document_id: uuid.UUID, db: DbSession) -> DocumentRead:
    row = await db.get(Document, document_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "code": "document_not_found",
                "message": f"No document found for {document_id}",
            },
        )
    return _document_read(row)


@router.post(
    "/{document_id}/reprocess",
    response_model=DocumentReprocessResponse,
    summary="Run OCR + clinical extraction on the retained original",
)
async def reprocess_document_endpoint(
    document_id: uuid.UUID, db: DbSession
) -> DocumentReprocessResponse:
    try:
        row = await reprocess_document(db, document_id)
    except HTTPException as exc:
        # Return the persisted failure state for OCR failures (502) so the
        # caller can read status=failed + error; other gates re-raise.
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        if detail.get("code") == "ocr_failed":
            row = await db.get(Document, document_id)
            if row is None:
                raise exc from None
            extraction = row.extraction or {}
            return DocumentReprocessResponse(
                document_id=row.id,
                session_id=row.session_id,
                status=row.processing_status,
                document_type=row.document_type,
                page_count=row.page_count,
                ocr_provider=row.ocr_provider,
                ocr_mocked=row.ocr_mocked,
                confidence=extraction.get("confidence"),
                extraction=row.extraction,
                processed_at=row.processed_at,
                error=row.last_error,
                message="OCR processing failed; the document is marked failed and can be retried.",
            )
        raise
    extraction = row.extraction or {}
    return DocumentReprocessResponse(
        document_id=row.id,
        session_id=row.session_id,
        status=row.processing_status,
        document_type=row.document_type,
        page_count=row.page_count,
        ocr_provider=row.ocr_provider,
        ocr_mocked=row.ocr_mocked,
        confidence=extraction.get("confidence"),
        extraction=row.extraction,
        processed_at=row.processed_at,
        error=None,
        message=(
            "OCR + extraction completed (mock provider — simulated text, not real OCR)."
            if row.ocr_mocked
            else "OCR + extraction completed with the real PaddleOCR engine."
        ),
    )
