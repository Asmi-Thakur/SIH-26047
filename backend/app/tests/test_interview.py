"""Phase 2b tests: deterministic touch interview flow.

Drives the full journey over the HTTP API: session -> consent -> answer every
question the state machine serves, asserting the SOCRATES-style conditional
HPI (complaint-specific questions) is applied and the session completes.
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
from app.models.clinical import Answer


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


def _new_session(client: TestClient) -> str:
    return client.post("/api/sessions", json={}).json()["session_id"]


def _choose_for(question: dict) -> dict:
    """Build a plausible touch answer body for any question."""
    if question["input"] == "text":
        return {"text": "Sample free-text answer"}
    codes = [c["code"] for c in question["choices"]]
    if question["input"] == "multi":
        return {"choice_codes": [codes[0]]}
    return {"choice_codes": [codes[0]]}


def _run_to_completion(client: TestClient, session_id: str, complaint_code: str):
    """Answer everything until completed=True; return asked question ids."""
    asked: list[str] = []
    answered: list[dict] = []

    for _ in range(50):  # guard against infinite loops
        nxt = client.get(f"/api/interview/{session_id}/next").json()
        assert nxt["completed"] is False, "flow completed before expected"
        q = nxt["question"]
        assert q is not None
        asked.append(q["question_id"])

        if q["question_id"] == "cc_001":
            body = {"choice_codes": [complaint_code]}
        else:
            body = _choose_for(q)
        body["input_mode"] = "touch"
        res = client.post(
            f"/api/interview/{session_id}/answer",
            json={"question_id": q["question_id"], **body},
        )
        assert res.status_code == 200, res.text
        answered.append(res.json())
        if res.json()["completed"]:
            return asked, answered[-1]

    raise AssertionError("interview did not complete within 50 answers")


def test_interview_requires_consent_first(client_with_db) -> None:
    client, _ = client_with_db
    session_id = _new_session(client)

    response = client.get(f"/api/interview/{session_id}/next")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "consent_required"

    missing = client.get(f"/api/interview/{uuid.uuid4()}/next")
    assert missing.status_code == 404


def test_full_touch_flow_with_chest_pain_hpi(client_with_db) -> None:
    client, maker = client_with_db
    session_id = _new_session(client)
    consent = client.post(
        f"/api/sessions/{session_id}/consent",
        json={"granted": True, "purposes": ["clinical_intake"]},
    )
    assert consent.status_code == 201

    asked, last = _run_to_completion(client, session_id, "chest_pain")

    # Chest pain triggers the conditional pain questions (site/radiation…).
    assert "hpi_005" in asked
    assert "hpi_006" in asked
    assert "hpi_007" in asked
    assert last["state"] == "documents"
    assert last["completed"] is True
    assert last["question"] is None

    # Completed session: further /next calls stay completed.
    again = client.get(f"/api/interview/{session_id}/next").json()
    assert again["completed"] is True
    assert again["question"] is None

    async def check_rows() -> None:
        async with maker() as session:
            count = await session.scalar(
                select(func.count()).select_from(Answer)
            )
            assert count == len(asked)

    asyncio.run(check_rows())


def test_adaptive_hpi_skips_pain_questions_for_fever(client_with_db) -> None:
    client, _ = client_with_db
    session_id = _new_session(client)
    client.post(
        f"/api/sessions/{session_id}/consent", json={"granted": True}
    )

    asked, _ = _run_to_completion(client, session_id, "fever")

    # Location/radiation/aggravation only apply to pain complaints.
    assert "hpi_005" not in asked
    assert "hpi_006" not in asked
    assert "hpi_007" not in asked


def test_wrong_question_order_is_rejected(client_with_db) -> None:
    client, _ = client_with_db
    session_id = _new_session(client)
    client.post(
        f"/api/sessions/{session_id}/consent", json={"granted": True}
    )

    nxt = client.get(f"/api/interview/{session_id}/next").json()
    assert nxt["question"]["question_id"] == "cc_001"

    # Try to answer a future question instead of the current one.
    wrong = client.post(
        f"/api/interview/{session_id}/answer",
        json={"question_id": "hpi_001", "choice_codes": ["hours"]},
    )
    assert wrong.status_code == 409
    assert wrong.json()["detail"]["code"] == "question_not_current"

    # Invalid choice for the current question is rejected too.
    bad_choice = client.post(
        f"/api/interview/{session_id}/answer",
        json={"question_id": "cc_001", "choice_codes": ["not_a_complaint"]},
    )
    assert bad_choice.status_code == 422
