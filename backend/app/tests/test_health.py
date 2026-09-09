"""Health endpoints and endpoint-lifecycle behaviour."""
import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def client_with_db():
    """App client over an in-memory sqlite DB with tables created."""
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


def test_liveness_root_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "medikiosk-backend"


def test_api_health_reports_database_state() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "medikiosk-backend"
    # In tests the engine may be backed by sqlite or an unreachable postgres —
    # either is acceptable; the endpoint must not 500.
    assert body["database"] in {"ok", "unavailable"}
    assert body["environment"] == "test"


def test_root_metadata() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "MediKiosk Backend"
    assert body["demo_mode"] is True
    assert body["api_health"] == "/api/health"


def test_previously_deferred_endpoints_are_now_real_or_structured(client_with_db) -> None:
    """Endpoints for later phases must answer 501, never a fake success.

    Sessions (2), interview (2b), triage (3b), speech (3c), LLM extraction
    (3d/2), document upload/status (4), the case endpoints (6), FHIR export
    (7) and document reprocess (4/2 — OCR) are all real now, covered by their
    own test modules. No 501 features remain; reprocess on an unknown
    document must answer the structured 404 (never a fake success).
    """
    doc_id = uuid.uuid4()

    response = client_with_db.post(f"/api/documents/{doc_id}/reprocess")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert detail["code"] == "document_not_found"
