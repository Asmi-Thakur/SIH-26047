"""LLM extraction endpoint schemas (Phase 3d/2)."""
from typing import Any

from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="en", max_length=8)


class ExtractionResponse(BaseModel):
    fields: dict[str, Any]
    provider: str
    mocked: bool  # true when output came from the deterministic fallback
