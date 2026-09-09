"""Triage endpoint schemas (Phase 3b)."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class TriageAlertRead(BaseModel):
    alert_id: uuid.UUID
    session_id: uuid.UUID
    priority: str
    status: str
    message: str | None = None
    rules_triggered: list[str] = []
    token: str | None = None
    chief_complaint: str | None = None
    created_at: datetime


class TriageActiveResponse(BaseModel):
    count: int
    items: list[TriageAlertRead]


class TriageAckResponse(BaseModel):
    alert_id: uuid.UUID
    status: str
