"""Speech endpoint schemas (Phase 3c — mock provider first)."""
from pydantic import BaseModel, Field


class TranscribeResponse(BaseModel):
    transcript: str
    language: str
    provider: str
    mocked: bool  # true when the transcript is simulated, not real ASR


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="en", max_length=8)
