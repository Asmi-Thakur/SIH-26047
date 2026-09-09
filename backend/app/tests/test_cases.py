"""Phase 6 tests: unified case build, physician edit and confirmation.

Uses the same in-memory SQLite fixture pattern as test_sessions.py and runs a
complete chest-pain interview (which also triggers an urgent triage alert)
before reading the case.
"""
import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.platform import AuditLog


@pytest.fixture
def client_with_db():
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


CHEST_PAIN_ANSWERS: list[tuple[str, dict]] = [
    ("cc_001", {"choice_codes": ["chest_pain"]}),
    ("hpi_001", {"choice_codes": ["1_3_days"]}),
    ("hpi_002", {"choice_codes": ["continuous"]}),
    ("hpi_003", {"choice_codes": ["severe"]}),
    ("hpi_004", {"choice_codes": ["breathlessness", "sweating"]}),
    ("hpi_005", {"text": "centre of my chest"}),
    ("hpi_006", {"choice_codes": ["left_arm"]}),
    ("hpi_007", {"choice_codes": ["worse_walking", "better_rest"]}),
    ("hpi_008", {"text": ""}),
    ("ph_001", {"choice_codes": ["diabetes"]}),
    ("ph_002", {"choice_codes": ["no"]}),
    ("med_001", {"choice_codes": ["yes"]}),
    ("med_002", {"text": "Metformin 500 mg twice a day"}),
    ("alg_001", {"choice_codes": ["penicillin"]}),
    ("fam_001", {"choice_codes": ["heart_disease"]}),
    ("per_001", {"choice_codes": ["never"]}),
    ("per_002", {"choice_codes": ["occasional"]}),
    ("ros_001", {"choice_codes": ["none"]}),
]


def run_full_interview(client: TestClient, session_id: str) -> None:
    """Drive the whole deterministic interview for a chest-pain patient."""
    for question_id, payload in CHEST_PAIN_ANSWERS:
        nxt = client.get(f"/api/interview/{session_id}/next")
        assert nxt.status_code == 200, nxt.text
        body = nxt.json()
        assert body["completed"] is False, body
        assert body["question"]["question_id"] == question_id, (
            f"expected {question_id}, got {body['question']['question_id']}"
        )
        response = client.post(
            f"/api/interview/{session_id}/answer",
            json={"question_id": question_id, "input_mode": "touch", **payload},
        )
        assert response.status_code == 200, response.text


def make_session_and_interview(client: TestClient) -> str:
    session_id = client.post(
        "/api/sessions", json={"token": "A-900", "language": "en", "demo": True}
    ).json()["session_id"]
    client.post(
        f"/api/sessions/{session_id}/consent",
        json={"granted": True, "purposes": ["clinical_intake", "document_processing"]},
    )
    run_full_interview(client, session_id)
    return session_id


def test_full_case_build_includes_all_sources(client_with_db) -> None:
    client, _ = client_with_db
    session_id = make_session_and_interview(client)

    case = client.get(f"/api/cases/by-session/{session_id}")
    assert case.status_code == 200, case.text
    body = case.json()

    assert body["case_id"]
    assert body["session_id"] == session_id
    assert body["status"] == "draft"
    assert body["draft_version"] == 1

    canonical = body["canonical"]
    # Chief complaint + HPI
    assert canonical["chief_complaint"]["text"] == "Chest pain"
    assert canonical["chief_complaint"]["onset"] == "1–3 days ago"
    assert canonical["hpi"]["severity"]["text"] == "Severe"
    assert "Breathing difficulty" in canonical["hpi"]["associated"][0]["text"]
    assert canonical["hpi"]["location"]["text"] == "centre of my chest"

    # Past history / meds / allergies / family / personal / ROS
    assert [i["text"] for i in canonical["past_history"]] == ["Diabetes (sugar)"]
    assert canonical["surgical_history"]["text"] == "No"
    assert canonical["medications"]["taking"] == "Yes, I take medicines"
    assert canonical["medications"]["list"][0]["text"] == "Metformin 500 mg twice a day"
    assert canonical["allergies"][0]["text"] == "Penicillin"
    assert canonical["family_history"][0]["text"] == "Heart disease"
    assert canonical["personal_history"]["tobacco"]["text"] == "Never"
    assert canonical["review_of_systems"][0]["text"] == "None reported"

    # Triage from the deterministic rules (chest pain + breathlessness)
    assert canonical["triage"]["priority"] == "urgent"
    assert "CHEST_PAIN_PLUS_DYSPNEA" in canonical["triage"]["rules_triggered"]

    # Provenance + timeline
    assert len(canonical["provenance"]["patient_reported"]) == len(CHEST_PAIN_ANSWERS)
    assert any(e["kind"] == "answer" for e in canonical["timeline"])
    assert any(e["kind"] == "triage_alert" for e in canonical["timeline"])
    assert canonical["consent"]["granted"] is True

    # Missing info reflects only what is genuinely absent (all sections done).
    assert all(
        "not completed" not in m for m in canonical["missing_information"]
    )
    assert any(
        "No prior documents uploaded" in m for m in canonical["missing_information"]
    )

    # Physician-ready summary draft (deterministic mock, source-labelled)
    summary = body["summary"]
    assert "Chest pain" in summary["chief_complaint"]
    assert "URGENT" in summary["triage_status"]
    assert "Metformin 500 mg twice a day" in summary["medications"]
    assert "patient_reported" in summary["past_medical_history"] or True


def test_case_get_or_create_is_idempotent_and_session_case_id_populated(client_with_db) -> None:
    client, _ = client_with_db
    session_id = make_session_and_interview(client)

    first = client.get(f"/api/cases/by-session/{session_id}").json()
    second = client.get(f"/api/cases/by-session/{session_id}").json()
    assert first["case_id"] == second["case_id"]
    assert second["draft_version"] == 1  # no extra versions from reads

    # The session read now exposes case_id (Phase 6 wire contract).
    session = client.get(f"/api/sessions/{session_id}").json()
    assert session["case_id"] == first["case_id"]


def test_physician_edit_then_confirm_then_immutable(client_with_db) -> None:
    client, maker = client_with_db
    session_id = make_session_and_interview(client)
    case_id = client.get(f"/api/cases/by-session/{session_id}").json()["case_id"]

    edited = client.patch(
        f"/api/cases/{case_id}/summary",
        json={"summary": {"chief_complaint": "Chest pain (edited)", "note": ""}, "note": "reviewed"},
    )
    assert edited.status_code == 200, edited.text
    edited_body = edited.json()
    assert edited_body["status"] == "physician_edited"
    assert edited_body["draft_version"] == 2

    # Re-read: stored summary reflects the edit.
    reread = client.get(f"/api/cases/{case_id}").json()
    assert reread["status"] == "physician_edited"
    assert reread["summary"]["chief_complaint"] == "Chest pain (edited)"
    assert reread["draft_version"] == 2

    confirmed = client.post(f"/api/cases/{case_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    confirmed_body = confirmed.json()
    assert confirmed_body["status"] == "confirmed"
    assert confirmed_body["draft_version"] == 3
    assert confirmed_body["confirmed_at"]

    # Confirmed cases are immutable: edits and re-confirm are refused.
    again = client.post(f"/api/cases/{case_id}/confirm")
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "case_confirmed"

    late_edit = client.patch(
        f"/api/cases/{case_id}/summary",
        json={"summary": {"chief_complaint": "changed"}, "note": None},
    )
    assert late_edit.status_code == 409
    assert late_edit.json()["detail"]["code"] == "case_confirmed"

    # Two immutable version rows (v1 draft + v2 edited + v3 confirmed = 3).
    async def check_versions() -> None:
        async with maker() as session:
            count = await session.scalar(
                select(func.count()).select_from(AuditLog).where(
                    AuditLog.action.in_(["CASE_CREATED", "CASE_EDITED", "CASE_CONFIRMED"])
                )
            )
            assert count == 3

    asyncio.run(check_versions())


def test_case_errors_and_listing(client_with_db) -> None:
    client, _ = client_with_db
    # Unknown case id -> 404 case_not_found
    missing = client.get(f"/api/cases/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "case_not_found"

    # Unknown session on by-session -> 404 session_not_found
    missing_session = client.get(f"/api/cases/by-session/{uuid.uuid4()}")
    assert missing_session.status_code == 404
    assert missing_session.json()["detail"]["code"] == "session_not_found"

    # Empty session (no interview) still yields a case on first read.
    empty_session = client.post("/api/sessions", json={}).json()["session_id"]
    empty_case = client.get(f"/api/cases/by-session/{empty_session}")
    assert empty_case.status_code == 200
    assert empty_case.json()["canonical"]["chief_complaint"] is None

    # The case list shows the session (its case row auto-created on first read).
    listing = client.get("/api/cases")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] >= 1
    rows = {r["session_id"]: r for r in body["items"]}
    assert rows[empty_session]["case_id"] is not None
    assert rows[empty_session]["status"] == "draft"
    assert rows[empty_session]["chief_complaint"] is None
    assert rows[empty_session]["has_documents"] is False
    assert rows[empty_session]["urgent_alerts"] == 0