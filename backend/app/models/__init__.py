"""SQLAlchemy ORM models.

Importing this package registers every table on ``Base.metadata`` (used by
Alembic autogenerate and by tests that create tables on a scratch engine).
"""
from app.models.case import CaseSummary, CaseVersion
from app.models.clinical import Answer, Document, TriageAlert
from app.models.intake import Consent, PatientSession
from app.models.patient import Patient
from app.models.platform import AuditLog, FhirExport, SyncQueue, User

__all__ = [
    "Patient",
    "PatientSession",
    "Consent",
    "Answer",
    "Document",
    "TriageAlert",
    "CaseSummary",
    "CaseVersion",
    "User",
    "AuditLog",
    "FhirExport",
    "SyncQueue",
]
