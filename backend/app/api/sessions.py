"""Session endpoints — Phase 2: create session, read state, record consent.

Real behaviour lives in app/services/sessions.py; this module only maps
HTTP <-> service calls. No AI involved at this stage.
"""
import uuid

from fastapi import APIRouter

from app.api.deps import DbSession
from app.models.clinical import Answer
from app.models.intake import Consent, PatientSession
from app.models.patient import Patient
from app.schemas.session import (
    ConsentCreate,
    ConsentRead,
    SessionCreate,
    SessionListItem,
    SessionListResponse,
    SessionRead,
)
from app.services import sessions as sessions_service
from app.services.cases import service as cases_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _session_read(db: DbSession, intake: PatientSession) -> SessionRead:
    """Map the ORM row (column ``id``) to the wire model (``session_id``).

    ``case_id`` is populated once a case summary row exists for the session
    (Phase 6 — created on first physician read).
    """
    return SessionRead(
        session_id=intake.id,
        patient_id=intake.patient_id,
        case_id=await cases_service.case_id_for_session(db, intake.id),
        state=intake.state,
        mode=intake.mode,
        department=intake.department,
        is_demo=intake.is_demo,
        started_at=intake.started_at,
        completed_at=intake.completed_at,
    )


def _consent_read(consent: Consent) -> ConsentRead:
    return ConsentRead(
        session_id=consent.session_id,
        granted=consent.granted,
        purposes=consent.purposes,
        consent_text_version=consent.consent_text_version,
        created_at=consent.created_at,
        revoked_at=consent.revoked_at,
    )


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List sessions for the physician queue",
)
async def list_sessions(db: DbSession) -> SessionListResponse:
    rows = await sessions_service.list_sessions_for_queue(db)
    items = [_session_list_item(*row) for row in rows]
    return SessionListResponse(count=len(items), items=items)


def _session_list_item(
    intake: PatientSession,
    patient: Patient | None,
    consent: Consent | None,
    chief_complaint: Answer | None,
) -> SessionListItem:
    raw = chief_complaint.raw_answer if chief_complaint else None
    return SessionListItem(
        session_id=intake.id,
        token=patient.external_token if patient else None,
        patient_name=patient.name if patient else None,
        age=patient.age if patient else None,
        language=patient.preferred_language if patient else None,
        department=intake.department,
        state=intake.state,
        consent_granted=consent.granted if consent else None,
        chief_complaint=raw,
        is_demo=intake.is_demo,
        started_at=intake.started_at,
        completed_at=intake.completed_at,
    )


@router.post(
    "",
    status_code=201,
    response_model=SessionRead,
    summary="Create a patient session",
)
async def create_session(payload: SessionCreate, db: DbSession) -> SessionRead:
    intake = await sessions_service.create_session(db, payload)
    return await _session_read(db, intake)


@router.get(
    "/{session_id}",
    response_model=SessionRead,
    summary="Get current session state",
)
async def get_session(session_id: uuid.UUID, db: DbSession) -> SessionRead:
    intake = await sessions_service.get_session(db, session_id)
    return await _session_read(db, intake)


@router.post(
    "/{session_id}/consent",
    status_code=201,
    response_model=ConsentRead,
    summary="Record consent decision",
)
async def record_consent(
    session_id: uuid.UUID, payload: ConsentCreate, db: DbSession
) -> ConsentRead:
    consent = await sessions_service.record_consent(db, session_id, payload)
    return _consent_read(consent)
