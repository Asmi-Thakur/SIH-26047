"""Phase 7 tests: FHIR export of confirmed cases.

Covers: 409 case_not_confirmed gating, bundle shape (required resources,
source provenance, Condition rule), persistence to ``fhir_exports`` and
GET-last-attempt behaviour, plus a failed-attempt path (mapper failure →
``failed`` row with an error, no 500 leak).
"""
import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.platform import AuditLog, FhirExport

from app.tests.test_cases import (
    CHEST_PAIN_ANSWERS,
    make_session_and_interview,
)


@pytest.fixture
def client_with_db(tmp_path):
    settings = get_settings()
    settings.upload_dir = str(tmp_path / "uploads")

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(prepare())

    async def override_get_db():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield TestClient(app), maker

    app.dependency_overrides.pop(get_db, None)
    asyncio.run(engine.dispose())


def _confirmed_case(client: TestClient) -> tuple[str, str]:
    session_id = make_session_and_interview(client)
    case_id = client.get(f"/api/cases/by-session/{session_id}").json()["case_id"]
    confirmed = client.post(f"/api/cases/{case_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    return session_id, case_id


def test_export_requires_confirmed_case(client_with_db) -> None:
    client, _ = client_with_db
    session_id = make_session_and_interview(client)
    case_id = client.get(f"/api/cases/by-session/{session_id}").json()["case_id"]

    response = client.post(f"/api/fhir/export/{case_id}")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "case_not_confirmed"

    # GET before any export → export: null
    status = client.get(f"/api/fhir/export/{case_id}")
    assert status.status_code == 200
    assert status.json()["export"] is None


def test_export_requires_consent(client_with_db) -> None:
    client, _ = client_with_db
    # Interview WITH consent, then revoke the decision (consent upsert) —
    # export must refuse once consent is not granted.
    session_id = make_session_and_interview(client)
    revoked = client.post(
        f"/api/sessions/{session_id}/consent",
        json={"granted": False, "purposes": []},
    )
    assert revoked.status_code == 201, revoked.text

    case_id = client.get(f"/api/cases/by-session/{session_id}").json()["case_id"]
    confirmed = client.post(f"/api/cases/{case_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text

    response = client.post(f"/api/fhir/export/{case_id}")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "consent_required"


def test_export_confirmed_case_bundle_shape_and_sources(client_with_db) -> None:
    client, _ = client_with_db
    session_id, case_id = _confirmed_case(client)

    # A real uploaded document so a DocumentReference is produced.
    upload = client.post(
        "/api/documents/upload",
        data={"session_id": session_id},
        files={"file": ("lab.png", b"png-bytes", "image/png")},
    )
    assert upload.status_code == 201, upload.text

    response = client.post(f"/api/fhir/export/{case_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["destination"] == "local"
    assert body["succeeded_at"]
    assert body["error"] is None

    bundle = body["bundle"]
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert bundle["timestamp"]

    resources = [e["resource"] for e in bundle["entry"]]
    by_type: dict[str, list[dict]] = {}
    for resource in resources:
        by_type.setdefault(resource["resourceType"], []).append(resource)

    # Required resource types present
    for resource_type in (
        "Patient",
        "Encounter",
        "Consent",
        "Composition",
        "Observation",
        "AllergyIntolerance",
        "MedicationStatement",
        "DocumentReference",
    ):
        assert resource_type in by_type, resource_type

    # Exactly one Patient / Encounter / Consent / Composition
    assert len(by_type["Patient"]) == 1
    assert len(by_type["Encounter"]) == 1
    assert len(by_type["Consent"]) == 1
    assert len(by_type["Composition"]) == 1

    # Patient carries the token identifier
    patient = by_type["Patient"][0]
    assert patient["identifier"][0]["value"] == "A-900"

    # Consent reflects granted (the chest-pain fixture grants consent)
    consent = by_type["Consent"][0]
    assert consent["status"] == "active"
    assert consent["provision"]["type"] == "permit"

    # AllergyIntolerance for Penicillin; MedicationStatement for Metformin
    allergy_codes = {a["code"]["text"] for a in by_type["AllergyIntolerance"]}
    assert "Penicillin" in allergy_codes
    medication_texts = {m["medicationCodeableConcept"]["text"] for m in by_type["MedicationStatement"]}
    assert "Metformin 500 mg twice a day" in medication_texts

    # NO Condition resources: the fixture has no physician_confirmed problems
    assert "Condition" not in by_type

    # Every resource carries the source provenance extension
    from app.services.fhir.mapper import FHIR_SOURCE_EXTENSION

    for resource in resources:
        extensions = resource.get("extension") or []
        assert any(ext.get("url") == FHIR_SOURCE_EXTENSION for ext in extensions), (
            resource["resourceType"]
        )

    # Sources are distinguishable and normalised
    sources = {
        ext["valueString"]
        for resource in resources
        for ext in (resource.get("extension") or [])
        if ext.get("url") == FHIR_SOURCE_EXTENSION
    }
    assert "patient_reported" in sources

    # Composition narrative sections mention the source inline
    composition = by_type["Composition"][0]
    section_titles = {s["title"] for s in composition["section"]}
    assert "Chief complaint" in section_titles
    complaint_section = next(s for s in composition["section"] if s["title"] == "Chief complaint")
    assert "patient reported" in complaint_section["text"]["div"]

    # urn:uuid references resolve to entries in the bundle
    entry_ids = {r["id"] for r in resources}
    for entry in bundle["entry"]:
        assert entry["fullUrl"] == f"urn:uuid:{entry['resource']['id']}"
    encounter = by_type["Encounter"][0]
    assert encounter["subject"]["reference"].replace("urn:uuid:", "") in entry_ids


def test_condition_only_from_physician_confirmed(client_with_db) -> None:
    """A physician_confirmed past-history item becomes a Condition; the same
    item as patient_reported does not."""
    from app.services.fhir.mapper import build_fhir_bundle

    base_case = {
        "case_id": uuid.uuid4(),
        "patient": {"token": "A-1", "age": 40},
        "consent": {"granted": True, "purposes": [], "timestamp": "2026-09-08T00:00:00+00:00"},
        "chief_complaint": {"text": "Chest pain", "source": "patient_touch"},
        "past_history": [],
    }

    # patient_reported only → no Condition
    reported = dict(base_case, past_history=[{"text": "Diabetes", "source": "patient_touch"}])
    bundle = build_fhir_bundle(reported, case_id=reported["case_id"], exported_at="2026-09-08T00:00:00+00:00")
    types = {e["resource"]["resourceType"] for e in bundle["entry"]}
    assert "Condition" not in types
    assert "Observation" in types

    # physician_confirmed → Condition appears
    confirmed = dict(base_case, past_history=[{"text": "Diabetes", "source": "physician_confirmed"}])
    bundle = build_fhir_bundle(confirmed, case_id=confirmed["case_id"], exported_at="2026-09-08T00:00:00+00:00")
    conditions = [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Condition"]
    assert len(conditions) == 1
    assert conditions[0]["code"]["text"] == "Diabetes"
    assert conditions[0]["verificationStatus"]["coding"][0]["code"] == "confirmed"


def test_export_persists_and_get_returns_last_attempt(client_with_db) -> None:
    client, maker = client_with_db
    _session_id, case_id = _confirmed_case(client)

    first = client.post(f"/api/fhir/export/{case_id}")
    assert first.status_code == 200
    export_id = first.json()["export_id"]

    # Row persisted as succeeded with the bundle stored
    async def check_row() -> FhirExport:
        async with maker() as session:
            row = await session.get(FhirExport, uuid.UUID(export_id))
            assert row is not None
            assert row.status == "succeeded"
            assert row.destination == "local"
            assert row.bundle is not None
            assert row.bundle["resourceType"] == "Bundle"
            assert row.attempted_at is not None
            assert row.succeeded_at is not None
            return row

    asyncio.run(check_row())

    # Audit trail
    async def check_audit() -> None:
        async with maker() as session:
            events = (
                await session.execute(
                    select(AuditLog).where(AuditLog.action == "FHIR_EXPORTED")
                )
            ).scalars().all()
            assert len(events) == 1
            assert str(events[0].entity_id) == case_id

    asyncio.run(check_audit())

    # GET returns the last attempt (without the full bundle payload)
    fetched = client.get(f"/api/fhir/export/{case_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["case_id"] == case_id
    assert body["export"]["export_id"] == export_id
    assert body["export"]["status"] == "succeeded"
    assert body["export"]["bundle"] is None  # payload kept for POST only

    # A second attempt replaces the "last" pointer
    second = client.post(f"/api/fhir/export/{case_id}")
    assert second.status_code == 200
    last = client.get(f"/api/fhir/export/{case_id}").json()
    assert last["export"]["export_id"] == second.json()["export_id"]


def test_failed_export_attempt_is_persisted(client_with_db, monkeypatch) -> None:
    client, maker = client_with_db
    _session_id, case_id = _confirmed_case(client)

    from app.services.fhir import export as export_service
    from app.services.fhir import mapper

    def boom(*args, **kwargs):
        raise RuntimeError("mapper exploded")

    monkeypatch.setattr(mapper, "build_fhir_bundle", boom)
    # The service imported the symbol directly — patch it there too.
    monkeypatch.setattr(export_service, "build_fhir_bundle", boom)

    response = client.post(f"/api/fhir/export/{case_id}")
    assert response.status_code == 200, response.text  # failure is a *result*, not a 500
    body = response.json()
    assert body["status"] == "failed"
    assert body["bundle"] is None
    assert "mapper exploded" in body["error"]
    assert body["succeeded_at"] is None

    async def check_row() -> None:
        async with maker() as session:
            rows = (
                await session.execute(
                    select(FhirExport).where(FhirExport.session_id == uuid.UUID(_session_id))
                )
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].status == "failed"
            assert rows[0].bundle is None
            assert "mapper exploded" in rows[0].error

    asyncio.run(check_row())

    # Failed attempts are audit-logged too
    async def check_audit() -> None:
        async with maker() as session:
            events = (
                await session.execute(
                    select(AuditLog).where(AuditLog.action == "FHIR_EXPORT_FAILED")
                )
            ).scalars().all()
            assert len(events) == 1

    asyncio.run(check_audit())

    # GET still works and shows the failed attempt
    last = client.get(f"/api/fhir/export/{case_id}").json()
    assert last["export"]["status"] == "failed"

    # And the case can be re-exported after fixing the mapper
    monkeypatch.undo()
    retry = client.post(f"/api/fhir/export/{case_id}")
    assert retry.status_code == 200
    assert retry.json()["status"] == "succeeded"


def test_export_unknown_case_404(client_with_db) -> None:
    client, _ = client_with_db
    missing = client.post(f"/api/fhir/export/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "case_not_found"
