"""Case service (Phase 6): persistence + lifecycle of the unified case.

A "case" is the ``case_summaries`` row for a session:

- created lazily on first physician read (``get_or_create_summary``) with the
  assembled content and an immutable ``case_versions`` snapshot (v1),
- edited by the physician (``patch_summary`` → ``physician_edited`` + new
  version + ``CASE_EDITED`` audit),
- locked by confirmation (``confirm_case`` → ``confirmed`` + immutable
  version + ``CASE_CONFIRMED`` audit). Confirmed content is never silently
  overwritten (ADR-007/ADR-009).

The stored content is ``{"canonical": {...}, "summary": {...}}`` where
``summary`` is the physician-edited text draft. The canonical side is
re-assembled from the answers on every read so the doctor always sees the
current patient-reported source of truth next to their draft.
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models.case import CaseSummary, CaseVersion
from app.models.clinical import Answer, Document, TriageAlert
from app.models.intake import Consent, PatientSession
from app.models.patient import Patient
from app.models.platform import AuditLog
from app.schemas.case import CaseListItem
from app.services.cases.builder import assemble_case

CONTENT_CANONICAL = "canonical"
CONTENT_SUMMARY = "summary"


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"status": "error", "code": code, "message": message},
    )


async def _session_context(
    db: AsyncSession, session_id: uuid.UUID
) -> tuple[PatientSession, Consent | None, list[Answer], list[Document], list[TriageAlert]]:
    session = await db.get(PatientSession, session_id)
    if session is None:
        raise _error(404, "session_not_found", f"No session found for {session_id}")

    consent = (
        await db.execute(select(Consent).where(Consent.session_id == session_id))
    ).scalar_one_or_none()
    answers = list(
        (
            await db.execute(
                select(Answer)
                .where(Answer.session_id == session_id)
                .order_by(Answer.created_at)
            )
        ).scalars()
    )
    documents = list(
        (
            await db.execute(
                select(Document).where(Document.session_id == session_id)
            )
        ).scalars()
    )
    alerts = list(
        (
            await db.execute(
                select(TriageAlert).where(TriageAlert.session_id == session_id)
            )
        ).scalars()
    )
    return session, consent, answers, documents, alerts


async def _build_content(
    db: AsyncSession,
    session: PatientSession,
    *,
    case_id: uuid.UUID,
    status: str,
    draft_version: int,
) -> dict:
    _, consent, answers, documents, alerts = await _session_context(db, session.id)
    assembled = await assemble_case(
        db,
        session,
        consent=consent,
        answers=answers,
        documents=documents,
        alerts=alerts,
        case_id=case_id,
        status=status,
        draft_version=draft_version,
    )
    return assembled  # {"canonical": ..., "summary": ...}


async def _summary_by_session(db: AsyncSession, session_id: uuid.UUID) -> CaseSummary | None:
    return (
        await db.execute(select(CaseSummary).where(CaseSummary.session_id == session_id))
    ).scalar_one_or_none()


async def get_or_create_summary(
    db: AsyncSession, session_id: uuid.UUID
) -> tuple[CaseSummary, bool]:
    """Return (summary_row, created). Creates the row + v1 snapshot on first read."""
    existing = await _summary_by_session(db, session_id)
    if existing is not None:
        return existing, False

    session, _, _, _, _ = await _session_context(db, session_id)
    summary = CaseSummary(session_id=session_id, status="draft", draft_version=1)
    db.add(summary)
    await db.flush()

    content = await _build_content(
        db, session, case_id=summary.id, status="draft", draft_version=1
    )
    summary.content = content
    db.add(
        CaseVersion(
            case_summary_id=summary.id,
            version_number=1,
            status="draft",
            content=content,
        )
    )
    db.add(
        AuditLog(
            actor_type="system",
            action="CASE_CREATED",
            entity_type="case_summary",
            entity_id=summary.id,
            details={"session_id": str(session_id)},
        )
    )
    await db.commit()
    await db.refresh(summary)
    return summary, True


async def get_case(db: AsyncSession, case_id: uuid.UUID) -> tuple[CaseSummary, PatientSession]:
    """Load the summary row and its session (404 case_not_found)."""
    summary = await db.get(CaseSummary, case_id)
    if summary is None:
        raise _error(404, "case_not_found", f"No case found for {case_id}")
    session = await db.get(PatientSession, summary.session_id)
    if session is None:
        raise _error(404, "session_not_found", "Case session missing")
    return summary, session


async def case_read_payload(
    db: AsyncSession, summary: CaseSummary, session: PatientSession
) -> dict:
    """Fresh canonical assembly + stored (edited) summary for the response."""
    assembled = await _build_content(
        db,
        session,
        case_id=summary.id,
        status=summary.status,
        draft_version=summary.draft_version,
    )
    content = summary.content or {}
    stored_summary = content.get(CONTENT_SUMMARY)
    if not isinstance(stored_summary, dict) or not stored_summary:
        # Older/empty rows: fall back to the freshly generated deterministic draft.
        stored_summary = assembled[CONTENT_SUMMARY]
    return {
        "case_id": summary.id,
        "session_id": summary.session_id,
        "status": summary.status,
        "draft_version": summary.draft_version,
        "canonical": assembled[CONTENT_CANONICAL],
        "summary": stored_summary,
        "updated_at": summary.updated_at,
        "confirmed_at": summary.confirmed_at,
    }


async def list_cases(db: AsyncSession) -> Sequence[CaseListItem]:
    """Physician case list: every session joined with patient/consent/complaint
    and its case summary row if one exists."""
    rows = await db.execute(
        select(PatientSession, Patient, Consent, Answer, CaseSummary)
        .outerjoin(Patient, Patient.id == PatientSession.patient_id)
        .outerjoin(Consent, Consent.session_id == PatientSession.id)
        .outerjoin(
            Answer,
            and_(
                Answer.session_id == PatientSession.id,
                Answer.question_id == "cc_001",
            ),
        )
        .outerjoin(CaseSummary, CaseSummary.session_id == PatientSession.id)
        .order_by(PatientSession.started_at.desc())
    )
    joined = rows.all()

    if not joined:
        return []

    session_ids = [r[0].id for r in joined]
    doc_counts = dict(
        (
            await db.execute(
                select(Document.session_id, func.count(Document.id))
                .where(Document.session_id.in_(session_ids))
                .group_by(Document.session_id)
            )
        ).all()
    )
    urgent_counts = dict(
        (
            await db.execute(
                select(TriageAlert.session_id, func.count(TriageAlert.id))
                .where(
                    and_(
                        TriageAlert.session_id.in_(session_ids),
                        TriageAlert.status == "active",
                        TriageAlert.priority == "urgent",
                    )
                )
                .group_by(TriageAlert.session_id)
            )
        ).all()
    )

    items: list[CaseListItem] = []
    for intake, patient, consent, complaint, summary in joined:
        items.append(
            CaseListItem(
                session_id=intake.id,
                case_id=summary.id if summary else None,
                token=patient.external_token if patient else None,
                patient_name=patient.name if patient else None,
                age=patient.age if patient else None,
                language=patient.preferred_language if patient else None,
                department=intake.department,
                state=intake.state,
                consent_granted=consent.granted if consent else None,
                chief_complaint=complaint.raw_answer if complaint else None,
                status=summary.status if summary else None,
                has_documents=doc_counts.get(intake.id, 0) > 0,
                urgent_alerts=urgent_counts.get(intake.id, 0),
                started_at=intake.started_at,
                completed_at=intake.completed_at,
                confirmed_at=summary.confirmed_at if summary else None,
            )
        )
    # Interviews in progress and confirmed cases first, then the rest.
    items.sort(key=lambda i: (0 if i.case_id else 1, i.confirmed_at is not None))
    return items


async def patch_summary(
    db: AsyncSession,
    case_id: uuid.UUID,
    summary_text: dict[str, str],
    note: str | None = None,
) -> CaseSummary:
    """Physician edit: merge the text draft, bump version, snapshot + audit.

    Refuses to edit a confirmed case (409 case_confirmed) — confirmed content
    is immutable (ADR-007).
    """
    summary, session = await get_case(db, case_id)
    if summary.status == "confirmed":
        raise _error(
            409,
            "case_confirmed",
            "This case is confirmed. Unlock (new session) to edit it again.",
        )

    content = dict(summary.content or {})
    stored = dict(content.get(CONTENT_SUMMARY) or {})
    stored.update(summary_text)
    content[CONTENT_SUMMARY] = stored

    summary.status = "physician_edited"
    summary.draft_version += 1
    summary.content = content
    summary.updated_at = utcnow()

    db.add(
        CaseVersion(
            case_summary_id=summary.id,
            version_number=summary.draft_version,
            status="physician_edited",
            content=content,
        )
    )
    db.add(
        AuditLog(
            actor_type="doctor",
            action="CASE_EDITED",
            entity_type="case_summary",
            entity_id=summary.id,
            details={
                "session_id": str(session.id),
                "version": summary.draft_version,
                "note": note,
            },
        )
    )
    await db.commit()
    await db.refresh(summary)
    return summary


async def confirm_case(
    db: AsyncSession, case_id: uuid.UUID, doctor_id: uuid.UUID | None = None
) -> CaseSummary:
    """Lock the case as the confirmed clinical record (immutable from here)."""
    summary, session = await get_case(db, case_id)
    if summary.status == "confirmed":
        raise _error(
            409,
            "case_confirmed",
            "This case is already confirmed.",
        )

    content = dict(summary.content or {})
    summary.status = "confirmed"
    summary.draft_version += 1
    summary.confirmed_at = utcnow()
    summary.confirmed_by = doctor_id
    summary.content = content

    db.add(
        CaseVersion(
            case_summary_id=summary.id,
            version_number=summary.draft_version,
            status="confirmed",
            content=content,
        )
    )
    db.add(
        AuditLog(
            actor_type="doctor",
            action="CASE_CONFIRMED",
            entity_type="case_summary",
            entity_id=summary.id,
            details={
                "session_id": str(session.id),
                "version": summary.draft_version,
            },
        )
    )
    await db.commit()
    await db.refresh(summary)
    return summary


async def case_id_for_session(db: AsyncSession, session_id: uuid.UUID) -> uuid.UUID | None:
    """case_id (case_summaries.id) for a session, if a case row exists."""
    summary = await _summary_by_session(db, session_id)
    return summary.id if summary else None