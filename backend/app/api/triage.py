"""Triage endpoints — Phase 3b (deterministic red-flag alerts)."""
import uuid

from fastapi import APIRouter

from app.api.deps import DbSession
from app.models.clinical import TriageAlert
from app.schemas.triage import (
    TriageAckResponse,
    TriageActiveResponse,
    TriageAlertRead,
)
from app.services.triage import alerts as triage_service

router = APIRouter(prefix="/triage", tags=["triage"])


def _alert_read(
    alert: TriageAlert, token: str | None, chief_complaint: str | None
) -> TriageAlertRead:
    return TriageAlertRead(
        alert_id=alert.id,
        session_id=alert.session_id,
        priority=alert.priority,
        status=alert.status,
        message=alert.message,
        rules_triggered=alert.rules_triggered or [],
        token=token,
        chief_complaint=chief_complaint,
        created_at=alert.created_at,
    )


@router.get(
    "/active",
    response_model=TriageActiveResponse,
    summary="Active urgent alerts for staff",
)
async def active_alerts(db: DbSession) -> TriageActiveResponse:
    rows = await triage_service.list_active(db)
    items = [_alert_read(alert, token, complaint) for alert, token, complaint in rows]
    return TriageActiveResponse(count=len(items), items=items)


@router.post(
    "/{alert_id}/acknowledge",
    response_model=TriageAckResponse,
    summary="Mark an alert as seen",
)
async def acknowledge_alert(alert_id: uuid.UUID, db: DbSession) -> TriageAckResponse:
    alert = await triage_service.acknowledge(db, alert_id)
    return TriageAckResponse(alert_id=alert.id, status=alert.status)
