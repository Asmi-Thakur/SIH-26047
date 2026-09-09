"""AYUSH Dashavidha Pariksha tests (spec §14, Phase 8).

Covers: department-gated questions (ayush sessions get the Dashavidha/
Ahara-Vihara section, others skip it), question-bank-only questions,
structured answers, the canonical case ``ayush`` block with provenance, the
physician summary section, and the disclaimer (no Ayurvedic diagnosis is
generated).
"""
import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.clinical.questions.loader import clear_bank_cache
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client_with_db():
    clear_bank_cache()
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
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    asyncio.run(engine.dispose())
    clear_bank_cache()


def _make_session(client: TestClient, department: str | None) -> str:
    session_id = client.post(
        "/api/sessions", json={"department": department}
    ).json()["session_id"]
    consent = client.post(
        f"/api/sessions/{session_id}/consent", json={"granted": True}
    )
    assert consent.status_code == 201
    return session_id


def _answer(client: TestClient, session_id: str, question_id: str, payload: dict) -> dict:
    nxt = client.get(f"/api/interview/{session_id}/next")
    assert nxt.status_code == 200, nxt.text
    body = nxt.json()
    assert body["question"]["question_id"] == question_id, (
        f"expected {question_id}, got {body['question'] and body['question']['question_id']}"
    )
    answer = client.post(
        f"/api/interview/{session_id}/answer",
        json={"question_id": question_id, "input_mode": "touch", **payload},
    )
    assert answer.status_code == 200, answer.text
    return answer.json()


AYUSH_ANSWERS: list[tuple[str, dict]] = [
    ("cc_001", {"choice_codes": ["joint_pain"]}),
    ("hpi_001", {"choice_codes": ["months"]}),
    ("hpi_002", {"choice_codes": ["intermittent"]}),
    ("hpi_003", {"choice_codes": ["moderate"]}),
    ("hpi_004", {"choice_codes": ["none"]}),
    ("hpi_005", {"text": "both knees"}),
    ("hpi_007", {"choice_codes": ["worse_walking"]}),
    ("hpi_008", {"text": ""}),
    ("ph_001", {"choice_codes": ["none"]}),
    ("ph_002", {"choice_codes": ["no"]}),
    ("med_001", {"choice_codes": ["no"]}),
    ("med_002", {"text": ""}),
    ("alg_001", {"choice_codes": ["none"]}),
    ("fam_001", {"choice_codes": ["none"]}),
    ("per_001", {"choice_codes": ["never"]}),
    ("per_002", {"choice_codes": ["never"]}),
    ("ros_001", {"choice_codes": ["none"]}),
    # Dashavidha / Ahara-Vihara structured captures:
    ("ay_001", {"choice_codes": ["good"]}),
    ("ay_002", {"choice_codes": ["moderate"]}),
    ("ay_003", {"choice_codes": ["all_foods"]}),
    ("ay_004", {"choice_codes": ["regular"]}),
    ("ay_005", {"choice_codes": ["disturbed"]}),
    ("ay_006", {"choice_codes": ["regular"]}),
    ("ay_007", {"choice_codes": ["low"]}),
    ("ay_008", {"choice_codes": ["sturdy"]}),
    ("ay_009", {"choice_codes": ["calm"]}),
    ("ay_010", {"choice_codes": ["normal"]}),
    ("ay_011", {"text": "mostly vegetarian diet"}),
]


def test_ayush_department_receives_dashavidha_questions(client_with_db) -> None:
    client = client_with_db
    session_id = _make_session(client, "ayush")

    # Drive the interview to completion; every bank question must be served.
    for question_id, payload in AYUSH_ANSWERS:
        _answer(client, session_id, question_id, payload)

    final = client.get(f"/api/interview/{session_id}/next").json()
    assert final["completed"] is True


def test_non_ayush_session_skips_ayush_section(client_with_db) -> None:
    client = client_with_db
    session_id = _make_session(client, None)

    # Answer everything except the ayush section; after ros the interview
    # must complete WITHOUT asking any ay_* question.
    for question_id, payload in AYUSH_ANSWERS:
        if question_id.startswith("ay_"):
            continue
        nxt = client.get(f"/api/interview/{session_id}/next").json()
        served = nxt["question"]["question_id"] if nxt["question"] else None
        assert served == question_id, f"expected {question_id}, got {served}"
        assert not served.startswith("ay_")
        client.post(
            f"/api/interview/{session_id}/answer",
            json={"question_id": question_id, "input_mode": "touch", **payload},
        )

    final = client.get(f"/api/interview/{session_id}/next").json()
    assert final["completed"] is True


def test_ayush_answers_reach_case_block_with_provenance(client_with_db) -> None:
    client = client_with_db
    session_id = _make_session(client, "ayush")
    for question_id, payload in AYUSH_ANSWERS:
        _answer(client, session_id, question_id, payload)

    case = client.get(f"/api/cases/by-session/{session_id}").json()
    canonical = case["canonical"]

    ayush = canonical["ayush"]
    assert ayush is not None
    assert ayush["collected"] is True
    assert ayush["department"] == "ayush"
    assert isinstance(ayush["items"], list) and len(ayush["items"]) >= 10

    by_question = {i["question_id"]: i for i in ayush["items"]}
    appetite = by_question["ay_001"]
    assert appetite["text"].startswith("Good")
    assert appetite["source"] == "patient_touch"
    assert appetite["field"]  # human-readable Dashavidha field label

    # Every provenance question id listed under patient_reported.
    for question_id in ("ay_001", "ay_005", "ay_007"):
        assert question_id in canonical["provenance"]["patient_reported"]

    # Summary surfaces the AYUSH history to the physician.
    assert case["summary"]["ayush_history"] != "Not collected"
    assert "[patient_touch]" in case["summary"]["ayush_history"]

    # The disclaimer is present — no autonomous Ayurvedic diagnosis.
    assert "does not determine an Ayurvedic diagnosis" in ayush["disclaimer"]

    # Chief complaint is the joint pain (routes to the AYUSH demo case).
    assert canonical["chief_complaint"]["code"] == "joint_pain"


def test_ayush_block_absent_without_answers(client_with_db) -> None:
    client = client_with_db
    session_id = _make_session(client, "ayush")

    case = client.get(f"/api/cases/by-session/{session_id}").json()
    assert case["canonical"]["ayush"] is None
    assert case["summary"]["ayush_history"] == "Not collected"


def test_ayush_bank_questions_are_structured_only(client_with_db) -> None:
    """Every AYUSH question must come from the bank with fixed choices."""
    from app.clinical.questions.loader import load_bank

    bank = load_bank()
    ayush_questions = [q for q in bank.questions if q.section == "ayush"]
    assert len(ayush_questions) >= 10
    for question in ayush_questions:
        assert question.department_for == ["ayush"]
        # Structured capture only: choice/multi — or an explicitly optional
        # text note. No free-form diagnostic generation.
        if question.input == "text":
            assert question.required is False
        else:
            assert question.choices, question.id
