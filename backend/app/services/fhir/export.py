"""FHIR export service (Phase 7).

Gates and lifecycle (ADR-007/011/018):

- Export is only allowed for a **confirmed** case (``409 case_not_confirmed``
  otherwise) — the physician's confirmation is what makes the record
  exportable.
- Consent must have been **granted** for the session (``409 consent_required``
  otherwise) — consent gating must never break.
- Every attempt is persisted in ``fhir_exports``: the row starts ``pending``,
  and ends ``succeeded`` (with the bundle) or ``failed`` (with the error),
  never silently dropped. ``destination`` records where the bundle went —
  for now always ``local``; a live FHIR server / ABDM push is a future
  ``HealthRecordAdapter`` (ADR-011) and must not be claimed until real.
- ``FHIR_EXPORTED`` / ``FHIR_EXPORT_FAILED`` audit events are written.

The bundle is built by ``mapper.build_fhir_bundle`` from the canonical case
re-assembled from recorded facts (ADR-005). This service is deterministic
and offline-safe; no network calls are made.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models.clinical import Answer, Document, TriageAlert
from app.models.intake import Consent
from app.models.patient import Patient
from app.models.platform import AuditLog, FhirExport
from app.services.cases.builder import build_canonical_case
from app.services.cases.service import get_case
from app.services.fhir.mapper import build_fhir_bundle

DESTINATION_LOCAL = "local"


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"status": "error", "code": code, "message": message},
    )


def _export_payload(row: FhirExport, case_id: uuid.UUID, include_bundle: bool) -> dict:
    payload: dict = {
        "export_id": row.id,
        "case_id": case_id,
        "session_id": row.session_id,
        "status": row.status,
        "destination": row.destination,
        "error": row.error,
        "attempted_at": row.attempted_at,
        "succeeded_at": row.succeeded_at,
        "created_at": row.created_at,
        "bundle": row.bundle if include_bundle else None,
        "message": (
            "FHIR R4 Bundle generated from the confirmed case."
            if row.status == "succeeded"
            else f"FHIR export {row.status}."
        ),
    }
    return payload


async def export_case(db: AsyncSession, case_id: uuid.UUID) -> tuple[FhirExport, dict]:
    """Export a confirmed case as a FHIR R4 Bundle.

    Returns ``(fhir_exports_row, bundle_dict)``. Raises:
    - 404 ``case_not_found`` (via the case service) for unknown cases,
    - 409 ``case_not_confirmed`` when the case is not yet confirmed,
    - 409 ``consent_required`` when consent was not granted.
    """
    summary, session = await get_case(db, case_id)

    if summary.status != "confirmed":
        raise _error(
            409,
            "case_not_confirmed",
            "Only confirmed cases can be exported to FHIR. Confirm the clinical record first.",
        )

    consent = (
        await db.execute(select(Consent).where(Consent.session_id == summary.session_id))
    ).scalar_one_or_none()
    if consent is None or not consent.granted:
        raise _error(
            409,
            "consent_required",
            "Patient consent has not been granted for this session; export is blocked.",
        )

    answers = list(
        (
            await db.execute(
                select(Answer)
                .where(Answer.session_id == summary.session_id)
                .order_by(Answer.created_at)
            )
        ).scalars()
    )
    documents = list(
        (
            await db.execute(
                select(Document).where(Document.session_id == summary.session_id)
            )
        ).scalars()
    )
    alerts = list(
        (
            await db.execute(
                select(TriageAlert).where(TriageAlert.session_id == summary.session_id)
            )
        ).scalars()
    )

    canonical = await build_canonical_case(
        db,
        session,
        patient=None,
        consent=consent,
        answers=answers,
        documents=documents,
        alerts=alerts,
        case_id=summary.id,
        status=summary.status,
        draft_version=summary.draft_version,
    )
    # The canonical builder leaves the patient block empty when `patient`
    # is None — resolve it here so demographics land in the Patient resource.
    patient = await db.get(Patient, session.patient_id) if session.patient_id else None
    if patient is not None:
        canonical["patient"] = {
            "patient_id": str(patient.id),
            "token": patient.external_token,
            "name": patient.name,
            "age": patient.age,
            "sex": patient.sex,
            "preferred_language": patient.preferred_language,
        }

    now = utcnow()
    row = FhirExport(
        session_id=summary.session_id,
        status="pending",
        destination=DESTINATION_LOCAL,
    )
    db.add(row)
    await db.flush()

    try:
        bundle = build_fhir_bundle(
            canonical,
            case_id=summary.id,
            exported_at=now.isoformat(),
        )
        row.bundle = bundle
        row.status = "succeeded"
        row.succeeded_at = now
        row.attempted_at = now
        db.add(
            AuditLog(
                actor_type="doctor",
                action="FHIR_EXPORTED",
                entity_type="case_summary",
                entity_id=summary.id,
                details={
                    "session_id": str(summary.session_id),
                    "export_id": str(row.id),
                    "destination": DESTINATION_LOCAL,
                    "bundle_entries": len(bundle.get("entry") or []),
                },
            )
        )
    except Exception as exc:  # noqa: BLE001 — persistence of failed attempts is required
        row.status = "failed"
        row.error = f"{type(exc).__name__}: {exc}"
        row.attempted_at = now
        db.add(
            AuditLog(
                actor_type="system",
                action="FHIR_EXPORT_FAILED",
                entity_type="case_summary",
                entity_id=summary.id,
                details={
                    "session_id": str(summary.session_id),
                    "export_id": str(row.id),
                    "error": row.error,
                },
            )
        )

    await db.commit()
    await db.refresh(row)
    return row, (row.bundle or {})


async def last_export_for_case(
    db: AsyncSession, case_id: uuid.UUID
) -> tuple[dict, FhirExport | None]:
    """Last export attempt for a case (404 case_not_found for unknown cases)."""
    summary, session = await get_case(db, case_id)
    row = (
        await db.execute(
            select(FhirExport)
            .where(FhirExport.session_id == session.id)
            .order_by(FhirExport.created_at.desc(), FhirExport.id.desc())
        )
    ).scalars().first()
    if row is None:
        return {"case_id": summary.id, "session_id": session.id, "export": None}, None
    return {
        "case_id": summary.id,
        "session_id": session.id,
        "export": _export_payload(row, summary.id, include_bundle=False),
    }, row


__all__ = ["export_case", "last_export_for_case", "DESTINATION_LOCAL"]
