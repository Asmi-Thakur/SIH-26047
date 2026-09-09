"""FHIR export endpoints (Phase 7).

- ``POST /fhir/export/{case_id}`` — map a **confirmed** case to a FHIR R4
  Bundle and persist the attempt (``fhir_exports``: pending → succeeded |
  failed). 409 ``case_not_confirmed`` until the physician confirms (ADR-007/018);
  409 ``consent_required`` without granted consent.
- ``GET /fhir/export/{case_id}`` — the last export attempt for the case
  (``export: null`` when never exported).

The bundle is stored with the export row; ABDM/live FHIR-server push stays a
future ``HealthRecordAdapter`` boundary (ADR-011) — this endpoint does NOT
claim live ABDM integration.
"""
import uuid

from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.fhir import FhirExportResponse, FhirExportStatusResponse
from app.services.fhir import export as fhir_export_service

router = APIRouter(prefix="/fhir", tags=["fhir"])


@router.post(
    "/export/{case_id}",
    response_model=FhirExportResponse,
    summary="Export a confirmed case as a FHIR R4 Bundle (requires confirmation + consent)",
)
async def export_case(case_id: uuid.UUID, db: DbSession) -> FhirExportResponse:
    row, _bundle = await fhir_export_service.export_case(db, case_id)
    return FhirExportResponse(
        export_id=row.id,
        case_id=case_id,
        session_id=row.session_id,
        status=row.status,
        destination=row.destination,
        error=row.error,
        attempted_at=row.attempted_at,
        succeeded_at=row.succeeded_at,
        created_at=row.created_at,
        bundle=row.bundle,
        message=(
            "FHIR R4 Bundle generated from the confirmed case."
            if row.status == "succeeded"
            else f"FHIR export {row.status}."
        ),
    )


@router.get(
    "/export/{case_id}",
    response_model=FhirExportStatusResponse,
    summary="Last FHIR export attempt for a case",
)
async def get_export(case_id: uuid.UUID, db: DbSession) -> FhirExportStatusResponse:
    payload, _row = await fhir_export_service.last_export_for_case(db, case_id)
    return FhirExportStatusResponse(**payload)
