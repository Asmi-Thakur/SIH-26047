"""Phase 4 tests: validated document upload + source retention."""
import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


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
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    asyncio.run(engine.dispose())


def test_upload_accepts_png_and_retains_source(client_with_db, tmp_path) -> None:
    client = client_with_db
    session_id = client.post("/api/sessions", json={}).json()["session_id"]

    content = b"%PDF-not-really-a-pdf-body-but-suffices"
    response = client.post(
        "/api/documents/upload",
        data={"session_id": session_id},
        files={"file": ("lab.png", content, "image/png")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["processing_status"] == "uploaded"
    assert body["sha256"] == __import__("hashlib").sha256(content).hexdigest()
    assert body["extraction"] is None

    # Original retained on disk, traceable via GET /documents/{id}.
    fetched = client.get(f"/api/documents/{body['document_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["file_name"] == "lab.png"
    stored = tmp_path / "uploads" / str(session_id) / f"{body['document_id']}.png"
    assert stored.exists()
    assert stored.read_bytes() == content


def test_upload_rejects_bad_type_and_missing_session(client_with_db, tmp_path) -> None:
    client = client_with_db
    session_id = client.post("/api/sessions", json={}).json()["session_id"]

    bad_type = client.post(
        "/api/documents/upload",
        data={"session_id": session_id},
        files={"file": ("virus.exe", b"MZ...", "application/octet-stream")},
    )
    assert bad_type.status_code == 415
    assert bad_type.json()["detail"]["code"] == "unsupported_media_type"

    missing_session = client.post(
        "/api/documents/upload",
        data={"session_id": str(uuid.uuid4())},
        files={"file": ("lab.png", b"x", "image/png")},
    )
    assert missing_session.status_code == 404
    assert missing_session.json()["detail"]["code"] == "session_not_found"
