"""Session lifecycle service (Phase 2).

Purely deterministic persistence — no AI involved:

- create a session (find-or-create the patient by OPD token),
- read the current session state,
- record the consent decision (single row per session, upsert on revisit).

The interview state machine (services/dialogue, Phase 2b) is what advances a
session past ``identity``. Consent never unlocks downstream processing on its
own — declining simply means later modules must not export/share records.
"""
import uuid
from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical import Answer
from app.models.intake import Consent, PatientSession
from app.models.patient import Patient
from app.models.platform import AuditLog
from app.schemas.session import ConsentCreate, SessionCreate, SessionListItem


def _not_found(session_id: uuid.UUID) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "code": "session_not_found",
            "message": f"No session found for {session_id}",
        },
    )


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> PatientSession:
    """Fetch a session by id or raise the standard 404 envelope."""
    row = await db.get(PatientSession, session_id)
    if row is None:
        raise _not_found(session_id)
    return row


async def create_session(
    db: AsyncSession, payload: SessionCreate
) -> PatientSession:
    """Create a session and its (find-or-create) patient record.

    State starts at ``identity``: the Welcome screen is pre-session, so a new
    journey always opens asking for hospital token / ABHA / walk-in.
    """
    patient: Patient | None = None
    if payload.token:
        result = await db.execute(
            select(Patient).where(Patient.external_token == payload.token)
        )
        patient = result.scalar_one_or_none()

    if patient is None:
        patient = Patient(
            external_token=payload.token,
            preferred_language=payload.language if payload.language else None,
        )
        db.add(patient)
    elif payload.language and patient.preferred_language != payload.language:
        patient.preferred_language = payload.language

    await db.flush()

    intake = PatientSession(
        patient_id=patient.id,
        department=payload.department,
        is_demo=payload.demo,
        state="identity",
    )
    db.add(intake)
    await db.flush()

    db.add(
        AuditLog(
            actor_type="system",
            action="SESSION_CREATED",
            entity_type="session",
            entity_id=intake.id,
            details={
                "is_demo": payload.demo,
                "has_token": bool(payload.token),
            },
        )
    )
    await db.commit()
    await db.refresh(intake)
    return intake


async def list_sessions_for_queue(db: AsyncSession) -> Sequence[tuple]:
    """All sessions joined with patient, consent and chief-complaint text.

    Returns ``(session, patient, consent, chief_complaint_answer)`` tuples
    ordered newest-first. The router maps them to ``SessionListItem``.
    """
    rows = await db.execute(
        select(PatientSession, Patient, Consent, Answer)
        .outerjoin(Patient, Patient.id == PatientSession.patient_id)
        .outerjoin(Consent, Consent.session_id == PatientSession.id)
        .outerjoin(
            Answer,
            and_(Answer.session_id == PatientSession.id, Answer.question_id == "cc_001"),
        )
        .order_by(PatientSession.started_at.desc())
    )
    # Active (not completed) visits first, then completed, each newest-first.
    result = list(rows.all())
    result.sort(key=lambda r: 1 if r[0].completed_at else 0)
    return result


async def record_consent(
    db: AsyncSession, session_id: uuid.UUID, payload: ConsentCreate
) -> Consent:
    """Upsert the single consent row for a session and audit the decision.

    Revisits (patient changed their mind on the kiosk) update the same row —
    the model enforces one consent per session with ``unique`` on session_id.
    """
    await get_session(db, session_id)

    existing = (
        await db.execute(select(Consent).where(Consent.session_id == session_id))
    ).scalar_one_or_none()

    if existing is None:
        consent = Consent(
            session_id=session_id,
            granted=payload.granted,
            purposes=payload.purposes,
            consent_text_version=payload.consent_text_version,
        )
        db.add(consent)
    else:
        existing.granted = payload.granted
        existing.purposes = payload.purposes
        existing.consent_text_version = payload.consent_text_version
        # A fresh grant clears any earlier revocation marker.
        existing.revoked_at = None
        consent = existing

    await db.flush()
    db.add(
        AuditLog(
            actor_type="patient",
            action="CONSENT_GRANTED" if payload.granted else "CONSENT_DECLINED",
            entity_type="consent",
            entity_id=consent.id,
            details={"session_id": str(session_id)},
        )
    )
    await db.commit()
    await db.refresh(consent)
    return consent
