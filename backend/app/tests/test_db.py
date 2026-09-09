"""Database connectivity/model tests.

These run against an in-memory SQLite database (aiosqlite) so `pytest` needs
no PostgreSQL. The models use a JSON variant that renders as JSONB on
PostgreSQL and JSON on SQLite (see app/db/base.py).
"""
import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.case import CaseSummary, CaseVersion
from app.models.clinical import Answer
from app.models.intake import Consent, PatientSession
from app.models.patient import Patient


def _make_engine():
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


def test_patient_and_session_roundtrip() -> None:
    async def run() -> None:
        engine = _make_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        maker = async_sessionmaker(engine, expire_on_commit=False)

        async with maker() as session:
            patient = Patient(name="Demo Patient", age=52, external_token="A-104")
            intake = PatientSession(department="ayush", is_demo=True)
            intake.patient_id = patient.id  # placeholder until relations exist
            session.add_all([patient, intake])
            await session.commit()

            patient_id = patient.id
            session_id = intake.id
            assert intake.state == "welcome"
            assert intake.is_demo is True

        async with maker() as session:
            fetched = await session.get(Patient, patient_id)
            assert fetched is not None
            assert fetched.name == "Demo Patient"
            assert fetched.age == 52
            assert fetched.external_token == "A-104"

        await engine.dispose()

    asyncio.run(run())


def test_consent_answer_case_and_version_roundtrip() -> None:
    async def run() -> None:
        engine = _make_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        maker = async_sessionmaker(engine, expire_on_commit=False)

        async with maker() as session:
            intake = PatientSession(department="general")
            session.add(intake)
            await session.commit()

            consent = Consent(
                session_id=intake.id,
                granted=True,
                purposes=["clinical_intake", "document_processing"],
            )
            answer = Answer(
                session_id=intake.id,
                question_id="cc_001",
                input_mode="touch",
                raw_answer="Chest pain",
                structured_value={"complaint": "chest_pain"},
                confidence=0.95,
                source="patient_touch",
            )
            case = CaseSummary(
                session_id=intake.id,
                content={"chief_complaint": {"text": "Chest pain"}},
            )
            session.add_all([consent, answer, case])
            await session.commit()

            version = CaseVersion(
                case_summary_id=case.id,
                version_number=1,
                content={"chief_complaint": {"text": "Chest pain"}},
            )
            session.add(version)
            await session.commit()

            assert consent.granted is True
            assert consent.purposes == ["clinical_intake", "document_processing"]
            assert answer.structured_value == {"complaint": "chest_pain"}
            assert case.status == "draft"
            assert case.draft_version == 1

        async with maker() as session:
            fetched = await session.get(CaseVersion, version.id)
            assert fetched is not None
            assert fetched.version_number == 1

        await engine.dispose()

    asyncio.run(run())
