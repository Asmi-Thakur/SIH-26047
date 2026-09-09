"""Phase 2 tests: session creation, state reads, and consent recording.

Each test gets its own in-memory SQLite engine (StaticPool so all requests
share one connection) wired in via ``get_db`` dependency override. No
PostgreSQL required.
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


def test_create_session_defaults(client_with_db) -> None:
    client, _ = client_with_db
    response = client.post("/api/sessions", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "identity"
    assert body["session_id"]
    uuid.UUID(body["session_id"])
    assert body["case_id"] is None
    assert body["is_demo"] is False
    assert body["department"] is None


def test_create_session_with_token_language_department(client_with_db) -> None:
    client, maker = client_with_db
    response = client.post(
        "/api/sessions",
        json={"token": "A-200", "language": "hi", "department": "ayush", "demo": True},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["department"] == "ayush"
    assert body["is_demo"] is True
    assert body["state"] == "identity"

    async def check_patient() -> None:
        async with maker() as session:
            result = await session.execute(
                select(AuditLog).where(AuditLog.action == "SESSION_CREATED")
            )
            assert result.scalar_one() is not None

    asyncio.run(check_patient())


def test_get_session_roundtrip_and_unknown_404(client_with_db) -> None:
    client, _ = client_with_db
    created = client.post("/api/sessions", json={"token": "A-201"}).json()

    fetched = client.get(f"/api/sessions/{created['session_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["session_id"] == created["session_id"]
    assert fetched.json()["state"] == "identity"

    missing = client.get(f"/api/sessions/{uuid.uuid4()}")
    assert missing.status_code == 404
    detail = missing.json()["detail"]
    assert detail["code"] == "session_not_found"


def test_record_consent_then_revise(client_with_db) -> None:
    client, maker = client_with_db
    session_id = client.post("/api/sessions", json={}).json()["session_id"]

    granted = client.post(
        f"/api/sessions/{session_id}/consent",
        json={
            "granted": True,
            "purposes": ["clinical_intake", "document_processing"],
            "consent_text_version": "v1",
        },
    )
    assert granted.status_code == 201
    assert granted.json()["granted"] is True
    assert granted.json()["session_id"] == session_id

    # A revised decision (upsert) must not create a second row.
    revised = client.post(
        f"/api/sessions/{session_id}/consent",
        json={"granted": False, "purposes": []},
    )
    assert revised.status_code == 201
    assert revised.json()["granted"] is False

    async def check_rows() -> None:
        async with maker() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action.in_(["CONSENT_GRANTED", "CONSENT_DECLINED"]))
            )
            assert count == 2  # granted then declined

    asyncio.run(check_rows())


def test_consent_on_unknown_session_404(client_with_db) -> None:
    client, _ = client_with_db
    response = client.post(
        f"/api/sessions/{uuid.uuid4()}/consent", json={"granted": True}
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "session_not_found"


def test_list_sessions_for_physician_queue(client_with_db) -> None:
    client, _ = client_with_db
    token_session = client.post(
        "/api/sessions", json={"token": "A-301"}
    ).json()["session_id"]
    walkin_session = client.post("/api/sessions", json={}).json()["session_id"]

    client.post(
        f"/api/sessions/{token_session}/consent", json={"granted": True}
    )
    # Record a chief complaint on the token session.
    nxt = client.get(f"/api/interview/{token_session}/next").json()
    assert nxt["question"]["question_id"] == "cc_001"
    client.post(
        f"/api/interview/{token_session}/answer",
        json={"question_id": "cc_001", "choice_codes": ["chest_pain"]},
    )

    listing = client.get("/api/sessions")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] == 2

    rows = {r["session_id"]: r for r in body["items"]}
    token_row = rows[token_session]
    assert token_row["token"] == "A-301"
    assert token_row["consent_granted"] is True
    assert token_row["chief_complaint"] == "Chest pain"

    walkin_row = rows[walkin_session]
    assert walkin_row["token"] is None
    assert walkin_row["consent_granted"] is None
    assert walkin_row["chief_complaint"] is None
