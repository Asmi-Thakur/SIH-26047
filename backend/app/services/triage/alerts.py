"""Triage alert service (Phase 3b).

Deterministic only: the rule evaluator runs over structured answers and the
service persists one ``triage_alerts`` row per (session, rule) while that
rule is still active. Acking marks it acknowledged so the staff view clears
it.
"""
import uuid
from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clinical.rules.evaluator import evaluate
from app.db.base import utcnow
from app.models.clinical import Answer, TriageAlert
from app.models.intake import PatientSession
from app.models.patient import Patient
from app.models.platform import AuditLog

ACTIVE = "active"


def _not_found(alert_id: uuid.UUID) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "status": "error",
            "code": "alert_not_found",
            "message": f"No triage alert found for {alert_id}",
        },
    )


async def create_alerts_for_answers(
    db: AsyncSession, session_id: uuid.UUID, recorded: dict[str, Answer]
) -> list[TriageAlert]:
    """Evaluate answers; persist alerts for rules not already flagged active."""
    matches = evaluate(recorded)

    active_rows = await db.execute(
        select(TriageAlert.rules_triggered).where(
            and_(
                TriageAlert.session_id == session_id,
                TriageAlert.status == ACTIVE,
            )
        )
    )
    already_flagged: set[str] = set()
    for (rules,) in active_rows.all():
        already_flagged.update(rules or [])

    created: list[TriageAlert] = []
    for match in matches:
        if match.rule_id in already_flagged:
            continue
        alert = TriageAlert(
            session_id=session_id,
            priority=match.priority,
            rules_triggered=[match.rule_id],
            message=match.message_en,
            status=ACTIVE,
        )
        db.add(alert)
        await db.flush()
        db.add(
            AuditLog(
                actor_type="system",
                action="RED_FLAG_CREATED",
                entity_type="triage_alert",
                entity_id=alert.id,
                details={"session_id": str(session_id), "rule_id": match.rule_id},
            )
        )
        created.append(alert)

    if created:
        await db.commit()
    return created


async def list_active(db: AsyncSession) -> Sequence[tuple]:
    """Active alerts with the session token and chief-complaint text.

    Returns ``(alert, token_or_None, chief_complaint_or_None)``, newest first.
    """
    rows = await db.execute(
        select(TriageAlert, Answer)
        .outerjoin(
            Answer,
            and_(
                Answer.session_id == TriageAlert.session_id,
                Answer.question_id == "cc_001",
            ),
        )
        .where(TriageAlert.status == ACTIVE)
        .order_by(TriageAlert.created_at.desc())
    )
    joined = rows.all()
    if not joined:
        return []

    session_ids = [alert.session_id for alert, _ in joined]
    token_rows = await db.execute(
        select(PatientSession.id, Patient.external_token)
        .outerjoin(Patient, Patient.id == PatientSession.patient_id)
        .where(PatientSession.id.in_(session_ids))
    )
    tokens = dict(token_rows.all())

    return [
        (
            alert,
            tokens.get(alert.session_id),
            cc.raw_answer if cc is not None else None,
        )
        for alert, cc in joined
    ]


async def acknowledge(db: AsyncSession, alert_id: uuid.UUID) -> TriageAlert:
    alert = await db.get(TriageAlert, alert_id)
    if alert is None:
        raise _not_found(alert_id)
    if alert.status == ACTIVE:
        alert.status = "acknowledged"
        alert.acknowledged_at = utcnow()
        await db.commit()
        await db.refresh(alert)
    return alert
