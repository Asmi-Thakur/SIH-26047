"""Case endpoints — Phase 6: unified case, physician summary, confirm.

- ``GET /cases`` — physician case list (every session + its case row).
- ``GET /cases/by-session/{session_id}`` — get-or-create the case for a
  session (used by the console which links from the queue by session id).
- ``GET /cases/{case_id}`` — full case (canonical + editable summary draft).
- ``PATCH /cases/{case_id}/summary`` — physician edits (409 once confirmed).
- ``POST /cases/{case_id}/confirm`` — lock the confirmed clinical record.

FHIR export (Phase 7) is gated on ``status == confirmed``.
"""
import uuid

from fastapi import APIRouter

from app.api.deps import DbSession
from app.models.intake import PatientSession
from app.schemas.case import (
    CaseActionResponse,
    CaseListResponse,
    CaseListItem,
    CaseRead,
    SummaryPatch,
)
from app.services.cases import service as cases_service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=CaseListResponse, summary="Physician case list")
async def list_cases(db: DbSession) -> CaseListResponse:
    items = await cases_service.list_cases(db)
    return CaseListResponse(count=len(items), items=list(items))


@router.get(
    "/by-session/{session_id}",
    response_model=CaseRead,
    summary="Get (or create) the case for a session",
)
async def get_case_by_session(session_id: uuid.UUID, db: DbSession) -> CaseRead:
    summary, _ = await cases_service.get_or_create_summary(db, session_id)
    return await _case_read(db, summary)


@router.get("/{case_id}", response_model=CaseRead, summary="Full case")
async def get_case(case_id: uuid.UUID, db: DbSession) -> CaseRead:
    summary, _ = await cases_service.get_case(db, case_id)
    return await _case_read(db, summary)


@router.patch(
    "/{case_id}/summary",
    response_model=CaseActionResponse,
    summary="Save physician edits to the summary draft",
)
async def patch_summary(case_id: uuid.UUID, payload: SummaryPatch, db: DbSession) -> CaseActionResponse:
    summary = await cases_service.patch_summary(db, case_id, payload.summary, payload.note)
    return _action_response(summary, "Summary draft saved.")


@router.post(
    "/{case_id}/confirm",
    response_model=CaseActionResponse,
    summary="Confirm the clinical record (locks the case, gates FHIR export)",
)
async def confirm_case(case_id: uuid.UUID, db: DbSession) -> CaseActionResponse:
    summary = await cases_service.confirm_case(db, case_id)
    return _action_response(summary, "Case confirmed as the clinical record.")


async def _case_read(db: DbSession, summary) -> CaseRead:
    session = await db.get(PatientSession, summary.session_id)
    payload = await cases_service.case_read_payload(db, summary, session)
    return CaseRead(**payload)


def _action_response(summary, message: str) -> CaseActionResponse:
    return CaseActionResponse(
        case_id=summary.id,
        session_id=summary.session_id,
        status=summary.status,
        draft_version=summary.draft_version,
        confirmed_at=summary.confirmed_at,
        message=message,
    )