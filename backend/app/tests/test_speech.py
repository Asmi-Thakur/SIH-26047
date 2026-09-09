"""Phase 3c tests: speech endpoints with the mock provider."""
from fastapi.testclient import TestClient

from app.main import app
from app.services.speech.mock import SAMPLE_EN, SAMPLE_HI


def test_transcribe_english_mock() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/speech/transcribe",
            files={"audio": ("sample.wav", b"\x00\x00", "audio/wav")},
            data={"language": "en"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == SAMPLE_EN
    assert "chest pain" in body["transcript"]
    assert body["provider"] == "mock"
    assert body["mocked"] is True


def test_transcribe_hindi_mock() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/speech/transcribe",
            files={"audio": ("sample.wav", b"\x00\x00", "audio/wav")},
            data={"language": "hi"},
        )
    assert response.status_code == 200
    assert response.json()["transcript"] == SAMPLE_HI


def test_transcribe_without_audio_file_still_works_in_mock() -> None:
    """The mock ignores audio; the endpoint must not 500 when it is absent."""
    with TestClient(app) as client:
        response = client.post(
            "/api/speech/transcribe", data={"language": "en"}
        )
    assert response.status_code == 200


def test_synthesize_returns_audio_wav() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/speech/synthesize",
            json={"text": "Welcome to the hospital", "language": "hi"},
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content[:4] == b"RIFF"
    assert len(response.content) > 100
