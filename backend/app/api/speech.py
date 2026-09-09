"""Speech endpoints — Phase 3c (mock provider first, DEMO_MODE safe).

POST /speech/transcribe : multipart audio + language -> transcript
POST /speech/synthesize : text + language -> audio bytes (WAV)

The provider registry picks the implementation from SPEECH_PROVIDER. The
default mock returns a deterministic bilingual transcript and a silent WAV,
so the full browser pipeline can be exercised with no API keys. Real ASR/TTS
vendors replace the mock transparently.
"""
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from app.schemas.speech import SynthesizeRequest, TranscribeResponse
from app.services.speech.registry import get_speech_provider

router = APIRouter(prefix="/speech", tags=["speech"])


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    summary="Transcribe audio via the configured SpeechProvider",
)
async def transcribe(
    language: str = Form(default="en"),
    audio: UploadFile | None = File(default=None),
) -> TranscribeResponse:
    provider, mocked = get_speech_provider()
    payload = await audio.read() if audio is not None else b""
    transcript = await provider.transcribe(payload, language=language)
    return TranscribeResponse(
        transcript=transcript,
        language=language,
        provider=provider.name,
        mocked=mocked,
    )


@router.post(
    "/synthesize",
    summary="Synthesize TTS audio for the given text",
    responses={200: {"content": {"audio/wav": {}}}},
)
async def synthesize(payload: SynthesizeRequest) -> Response:
    provider, _ = get_speech_provider()
    audio = await provider.synthesize(payload.text, language=payload.language)
    return Response(content=audio, media_type="audio/wav")
