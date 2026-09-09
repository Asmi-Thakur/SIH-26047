"""Phase 3b tests: deterministic red-flag triage.

Drives the interview until a structured symptom triggers a rule, then checks
the alert appears in GET /api/triage/active and can be acknowledged.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


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


def _run_flow(client: TestClient, session_id: str, complaint: str, associated: list[str]) -> None:
    """Answer through the interview, controlling cc_001 and hpi_004."""
    for _ in range(50):
        nxt = client.get(f"/api/interview/{session_id}/next").json()
        assert not nxt["completed"], "flow completed before expected"
        q = nxt["question"]
        qid = q["question_id"]
        if qid == "cc_001":
            body = {"choice_codes": [complaint]}
        elif qid == "hpi_004":
            body = {"choice_codes": associated}
        elif q["input"] == "text":
            body = {"text": "Sample"}
        elif q["input"] == "multi":
            body = {"choice_codes": [q["choices"][0]["code"]]}
        else:
            body = {"choice_codes": [q["choices"][0]["code"]]}
        res = client.post(
            f"/api/interview/{session_id}/answer",
            json={"question_id": qid, **body},
        )
        assert res.status_code == 200, res.text
        if res.json()["completed"]:
            return
    raise AssertionError("interview did not complete")


def _new_session_with_consent(client: TestClient) -> str:
    session_id = client.post("/api/sessions", json={"token": "T-900"}).json()[
        "session_id"
    ]
    client.post(
        f"/api/sessions/{session_id}/consent", json={"granted": True}
    )
    return session_id


def test_chest_pain_plus_breathlessness_flags_urgent(client_with_db) -> None:
    client, _ = client_with_db
    session_id = _new_session_with_consent(client)

    _run_flow(client, session_id, "chest_pain", ["breathlessness"])

    active = client.get("/api/triage/active")
    assert active.status_code == 200
    body = active.json()
    assert body["count"] == 1
    alert = body["items"][0]
    assert alert["rules_triggered"] == ["CHEST_PAIN_PLUS_DYSPNEA"]
    assert alert["priority"] == "urgent"
    assert "breathing difficulty" in alert["message"]
    assert alert["token"] == "T-900"
    assert alert["chief_complaint"] == "Chest pain"

    # Acknowledge clears the active queue.
    ack = client.post(f"/api/triage/{alert['alert_id']}/acknowledge")
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"
    assert client.get("/api/triage/active").json()["count"] == 0

    # Re-running answers must not re-flag while acknowledged is fine (already
    # acknowledged) — the interview is complete, so nothing more is answered.


def test_stroke_like_and_negative_cases(client_with_db) -> None:
    client, _ = client_with_db

    stroke_session = _new_session_with_consent(client)
    _run_flow(client, stroke_session, "headache", ["facial_weakness"])
    stroke = client.get("/api/triage/active").json()
    assert any(
        "STROKE_LIKE_SYMPTOMS" in a["rules_triggered"]
        for a in stroke["items"]
    )

    # Chest pain WITHOUT breathlessness must not trigger the combo rule.
    calm_session = _new_session_with_consent(client)
    _run_flow(client, calm_session, "chest_pain", ["none"])
    calm = client.get("/api/triage/active").json()
    calm_ids = [a["session_id"] for a in calm["items"]]
    assert calm_session not in calm_ids
