"""Phase 3d/2 tests: structured extraction from free-text narration."""
from fastapi.testclient import TestClient

from app.main import app


def test_extract_structured_fields_from_narration() -> None:
    """Spec example: 'diabetes + metformin + dizzy since yesterday'."""
    with TestClient(app) as client:
        response = client.post(
            "/api/llm/extract",
            json={
                "text": (
                    "I have diabetes and take metformin. "
                    "I have been feeling dizzy since yesterday."
                ),
                "language": "en",
            },
        )

    assert response.status_code == 200
    body = response.json()
    fields = body["fields"]
    assert body["mocked"] is True  # deterministic extractor in demo mode
    assert body["provider"] == "mock"
    assert "dizziness" in fields["complaint"]
    assert fields["duration"] == "1 day"
    assert "diabetes" in fields["conditions"]
    assert "Metformin" in fields["medications"]
    assert fields["missing_information"]  # follow-ups still needed


def test_extract_hindi_narration() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/llm/extract",
            json={
                "text": "मुझे तीन दिन से सीने में दर्द है और सांस लेने में तकलीफ है।",
                "language": "hi",
            },
        )

    assert response.status_code == 200
    fields = response.json()["fields"]
    assert "chest_pain" in fields["complaint"]
    assert "breathlessness" in fields["complaint"]
    assert fields["duration"] == "3 days"


def test_extract_short_text_lists_missing_fields() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/llm/extract", json={"text": "Not feeling well", "language": "en"}
        )
    fields = response.json()["fields"]
    assert fields["complaint"] == []
    assert any("chief complaint" in m for m in fields["missing_information"])
