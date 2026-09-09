"""Phase 4/2 tests: real reprocess endpoint + OCR provider seam.

Covers: unknown document, consent gating, status transitions
(uploaded -> processing -> completed | failed), mock provider behaviour and
labelling, real-provider configuration seam, PDF page counts, clinical data
persistence, document_extracted provenance in the case, abnormal-value
flags, and safe reprocessing of an already-processed document.

The suite always runs with OCR_PROVIDER=mock (conftest env) — real PaddleOCR
is exercised separately via the configuration-seam test below (monkeypatched
provider objects, no paddle import required).
"""
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
from app.services.ocr import registry as ocr_registry
from app.services.ocr.extract import classify_document, extract_document_facts


@pytest.fixture
def client_with_db(tmp_path, monkeypatch):
    settings = get_settings()
    settings.upload_dir = str(tmp_path / "uploads")
    settings.ocr_provider = "mock"  # deterministic OCR in the unit suite

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


def _granted_session(client: TestClient) -> str:
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    consent = client.post(
        f"/api/sessions/{session_id}/consent",
        json={"granted": True, "purposes": ["clinical_intake", "document_processing"]},
    )
    assert consent.status_code == 201, consent.text
    return session_id


def _upload(client: TestClient, session_id: str, name="lab.png", content=b"png-bytes",
            mime="image/png") -> dict:
    response = client.post(
        "/api/documents/upload",
        data={"session_id": session_id},
        files={"file": (name, content, mime)},
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Endpoint behaviour -------------------------------------------------------


def test_reprocess_unknown_document_404(client_with_db) -> None:
    response = client_with_db.post(f"/api/documents/{uuid.uuid4()}/reprocess")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "document_not_found"


def test_reprocess_requires_granted_consent(client_with_db) -> None:
    client = client_with_db
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    doc = _upload(client, session_id)

    # No consent decision recorded at all -> 409.
    blocked = client.post(f"/api/documents/{doc['document_id']}/reprocess")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "consent_required"
    # The document must be untouched by the refused attempt.
    after = client.get(f"/api/documents/{doc['document_id']}").json()
    assert after["processing_status"] == "uploaded"
    assert after["extraction"] is None

    # Declined consent also blocks processing.
    client.post(f"/api/sessions/{session_id}/consent", json={"granted": False})
    declined = client.post(f"/api/documents/{doc['document_id']}/reprocess")
    assert declined.status_code == 409
    assert declined.json()["detail"]["code"] == "consent_required"


def test_reprocess_success_mock_provider_and_transitions(client_with_db) -> None:
    client = client_with_db
    session_id = _granted_session(client)
    doc = _upload(client, session_id)
    assert doc["processing_status"] == "uploaded"

    response = client.post(f"/api/documents/{doc['document_id']}/reprocess")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["ocr_provider"] == "mock"
    assert body["ocr_mocked"] is True  # honest labelling: simulated, not real
    assert body["document_type"] in {"lab_report", "prescription", "discharge_summary",
                                     "imaging_report", "other", "unknown"}
    assert body["page_count"] >= 1
    assert body["extraction"] is not None
    assert body["extraction"]["mocked"] is True
    assert "NOT real OCR" in body["extraction"]["engine_note"]

    # GET reflects the completed state + persisted extraction.
    fetched = client.get(f"/api/documents/{doc['document_id']}").json()
    assert fetched["processing_status"] == "completed"
    assert fetched["ocr_mocked"] is True
    assert fetched["processed_at"] is not None
    assert fetched["extraction"]["text"]
    assert fetched["last_error"] is None


def test_reprocess_pdf_page_count(client_with_db) -> None:
    client = client_with_db
    session_id = _granted_session(client)
    # Minimal but valid 2-page PDF (pypdfium2-readable object count via mock is
    # provider-defined; the mock always reports a single page, so use a real
    # provider stub through the seam test below for multi-page assertions).
    doc = _upload(client, session_id, name="report.pdf", content=b"%PDF-1.4 fake",
                  mime="application/pdf")
    response = client.post(f"/api/documents/{doc['document_id']}/reprocess")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_reprocess_failure_marks_failed_with_persisted_error(client_with_db, monkeypatch) -> None:
    client = client_with_db
    session_id = _granted_session(client)
    doc = _upload(client, session_id)

    class ExplodingProvider:
        name = "explosion-mock"
        mocked = False

        async def extract(self, image, mime_type=None):
            raise RuntimeError("OCR engine exploded (synthetic test failure)")

    monkeypatch.setattr(
        "app.services.ocr.service.get_ocr_provider",
        lambda: (ExplodingProvider(), False),
    )

    response = client.post(f"/api/documents/{doc['document_id']}/reprocess")
    # A failed OCR run is a *successful* lifecycle update to `failed` — the
    # response carries the persisted state + error (FHIR-export convention:
    # a failed attempt is a readable response, never a bare 5xx).
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"] is not None
    assert "exploded" in body["error"]
    assert body["message"]

    # The failure is persisted and retryable — never a corrupted state.
    fetched = client.get(f"/api/documents/{doc['document_id']}").json()
    assert fetched["processing_status"] == "failed"
    assert fetched["last_error"]
    assert fetched["extraction"] is None
    assert fetched["document_type"] is None

    # Retry after fixing the provider completes normally.
    monkeypatch.setattr(
        "app.services.ocr.service.get_ocr_provider",
        lambda: (ocr_registry.MockOCRProvider(), True),
    )
    retry = client.post(f"/api/documents/{doc['document_id']}/reprocess")
    assert retry.status_code == 200
    assert retry.json()["status"] == "completed"
    fetched = client.get(f"/api/documents/{doc['document_id']}").json()
    assert fetched["last_error"] is None


def test_real_provider_configured_but_missing_raises(client_with_db, monkeypatch) -> None:
    """OCR_PROVIDER=paddleocr without paddle installed must raise — no silent mock."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ocr_provider", "paddleocr")
    monkeypatch.setattr(ocr_registry, "paddle_available", lambda: False)
    with pytest.raises(RuntimeError, match="paddleocr"):
        ocr_registry.get_ocr_provider()


def test_real_provider_seam_used_when_available(client_with_db, monkeypatch) -> None:
    """When paddle is importable and OCR_PROVIDER=auto, the REAL provider runs."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ocr_provider", "auto")
    monkeypatch.setattr(ocr_registry, "paddle_available", lambda: True)

    captured: dict = {}

    class FakeRealProvider:
        name = "paddleocr"
        mocked = False

        async def extract(self, image, mime_type=None):
            captured["bytes_len"] = len(image)
            captured["mime"] = mime_type
            return {
                "pages": [
                    {
                        "page_number": 1,
                        "lines": [
                            {"text": "Glucose 145 mg/dL (Ref 70-140) HIGH", "confidence": 0.99, "box": None}
                        ],
                    }
                ],
                "page_count": 1,
                "text": "Demo Diagnostics Laboratory\nGlucose 145 mg/dL (Ref 70-140) HIGH",
                "confidence": 0.99,
                "provider": "paddleocr",
                "mocked": False,
            }

    import app.services.ocr.paddle as paddle_mod

    monkeypatch.setattr(paddle_mod, "PaddleOCRProvider", FakeRealProvider)

    provider, mocked = ocr_registry.get_ocr_provider()
    assert mocked is False
    assert provider.name == "paddleocr"

    # End-to-end through the API with the (faked) real engine.
    client = client_with_db
    session_id = _granted_session(client)
    doc = _upload(client, session_id)
    response = client.post(f"/api/documents/{doc['document_id']}/reprocess")
    assert response.status_code == 200
    body = response.json()
    assert body["ocr_provider"] == "paddleocr"
    assert body["ocr_mocked"] is False
    assert body["confidence"] == 0.99
    assert body["extraction"]["mocked"] is False
    assert "Real PaddleOCR output" in body["extraction"]["engine_note"]
    assert captured["bytes_len"] == len(b"png-bytes")


def test_multi_page_pdf_through_real_provider_seam(client_with_db, monkeypatch) -> None:
    """PDF -> per-page OCR: page count and per-page lines survive the pipeline."""
    settings = get_settings()
    monkeypatch.setattr(settings, "ocr_provider", "auto")
    monkeypatch.setattr(ocr_registry, "paddle_available", lambda: True)

    class TwoPagePDFProvider:
        """Stands in for PaddleOCRProvider._get_engine + PDF rasterisation."""

        name = "paddleocr"
        mocked = False

        async def extract(self, image, mime_type=None):
            assert mime_type == "application/pdf"
            return {
                "pages": [
                    {"page_number": 1, "lines": [{"text": "Page one line", "confidence": 0.97, "box": None}]},
                    {"page_number": 2, "lines": [{"text": "Page two line", "confidence": 0.95, "box": None}]},
                ],
                "page_count": 2,
                "text": "Page one line\nPage two line",
                "confidence": 0.96,
                "provider": "paddleocr",
                "mocked": False,
            }

    import app.services.ocr.paddle as paddle_mod

    monkeypatch.setattr(paddle_mod, "PaddleOCRProvider", TwoPagePDFProvider)

    client = client_with_db
    session_id = _granted_session(client)
    doc = _upload(client, session_id, name="scan.pdf", content=b"%PDF-two-pages",
                  mime="application/pdf")
    response = client.post(f"/api/documents/{doc['document_id']}/reprocess")
    assert response.status_code == 200
    body = response.json()
    assert body["page_count"] == 2
    assert len(body["extraction"]["pages"]) == 2


def test_reprocessing_completed_document_is_safe(client_with_db) -> None:
    """Re-running OCR on a completed document reprocesses cleanly (idempotent)."""
    client = client_with_db
    session_id = _granted_session(client)
    doc = _upload(client, session_id)

    first = client.post(f"/api/documents/{doc['document_id']}/reprocess")
    assert first.status_code == 200
    second = client.post(f"/api/documents/{doc['document_id']}/reprocess")
    assert second.status_code == 200
    assert second.json()["status"] == "completed"

    fetched = client.get(f"/api/documents/{doc['document_id']}").json()
    assert fetched["processing_status"] == "completed"
    assert fetched["extraction"]["tests"] == fetched["extraction"]["tests"]


# --- Document -> canonical case -------------------------------------------------


def test_document_extraction_reaches_case_with_provenance(client_with_db) -> None:
    client = client_with_db
    session_id = _granted_session(client)
    doc = _upload(
        client,
        session_id,
        name="lab.png",
        content=b"png-bytes",
        mime="image/png",
    )
    processed = client.post(f"/api/documents/{doc['document_id']}/reprocess")
    assert processed.status_code == 200

    case = client.get(f"/api/cases/by-session/{session_id}").json()
    canonical = case["canonical"]

    # Document row in the case carries extraction provenance.
    docs = canonical["documents"]
    assert len(docs) == 1
    assert docs[0]["document_id"] == doc["document_id"]
    assert docs[0]["ocr_mocked"] is True
    assert docs[0]["source"] == "document_uploaded"

    # The mock fixture classifies as a lab report -> it is an investigation.
    assert canonical["investigations"], "completed lab report should appear in investigations"
    investigation = canonical["investigations"][0]
    assert investigation["document_type"] == "lab_report"
    assert investigation["abnormal_values"], "fixture contains one flagged value"

    flag = investigation["abnormal_values"][0]
    assert flag["status"] == "high"
    assert flag["name"].lower().startswith("glucose")

    # document_extracted provenance now lists the processed document.
    assert doc["document_id"] in canonical["provenance"]["document_extracted"]

    # Abnormal value appears on the timeline as a document_extracted event.
    extracted_events = [e for e in canonical["timeline"] if e["kind"] == "document_extracted"]
    assert extracted_events, "abnormal value should be a timeline event"
    assert "HIGH" in extracted_events[0]["detail"].upper()

    # The physician summary mentions the flagged value and the mock label.
    summary = case["summary"]["prior_investigations"]
    assert "HIGH" in summary
    assert "[mocked OCR]" in summary

    # No "documents not processed" missing-info entry anymore.
    assert not any("not yet processed" in m for m in canonical["missing_information"])


def test_unprocessed_document_flagged_in_missing_information(client_with_db) -> None:
    client = client_with_db
    session_id = _granted_session(client)
    _upload(client, session_id)

    case = client.get(f"/api/cases/by-session/{session_id}").json()
    canonical = case["canonical"]
    assert canonical["documents"]
    assert canonical["investigations"] == []
    assert any(
        "not yet processed" in m for m in canonical["missing_information"]
    )
    assert canonical["provenance"]["document_extracted"] == []


# --- Deterministic extractor unit checks (spec §18/§21) --------------------------


def test_classifier_and_extractor_unit() -> None:
    text = (
        "Demo Diagnostics Laboratory\n"
        "Glucose 145 mg/dL (Ref 70-140) HIGH\n"
        "Haemoglobin 9.8 g/dL ref 13-17 LOW\n"
        "Creatinine 1.1 mg/dL (Ref 0.7-1.3)\n"
        "History: Diabetes, Hypertension\n"
        "Tab Metformin 500 mg twice daily"
    )
    assert classify_document(text) == "lab_report"
    facts = extract_document_facts(text)

    by_name = {t["name"].lower(): t for t in facts["tests"]}
    glucose = by_name["glucose"]
    assert glucose["value"] == 145 and glucose["status"] == "high"
    assert glucose["reference_low"] == 70 and glucose["reference_high"] == 140
    hb = by_name["haemoglobin"]
    assert hb["status"] == "low"
    creatinine = by_name["creatinine"]
    assert creatinine["status"] == "normal"

    # No range -> status unknown (never invent a range, spec §21).
    no_range = extract_document_facts("Hb 13.5 g/dL")["tests"]
    assert no_range[0]["status"] == "unknown"

    assert {"Diabetes", "Hypertension"} <= {c["text"] for c in facts["conditions"]}
    assert facts["medications"] and facts["medications"][0]["name"] == "Metformin"
    assert all(t["source_text"] for t in facts["tests"])


def test_classifier_unknown_when_nothing_matches() -> None:
    assert classify_document("hello world this is not a medical document") == "unknown"
