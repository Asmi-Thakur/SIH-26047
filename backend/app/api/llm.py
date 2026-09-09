"""LLM extraction endpoint (Phase 3d/2).

POST /llm/extract : free-text narration -> structured extraction fields.
Provider chosen by LLM_PROVIDER (mock default); Gemini used when configured.
"""
from fastapi import APIRouter

from app.api.deps import AppSettings
from app.schemas.llm import ExtractionRequest, ExtractionResponse
from app.services.llm import extraction as llm_service

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    summary="Structured clinical extraction from free text (mock default)",
)
async def extract(
    payload: ExtractionRequest, settings: AppSettings
) -> ExtractionResponse:
    fields, provider, mocked = await llm_service.run_extraction(
        payload.text, payload.language, settings
    )
    return ExtractionResponse(fields=fields, provider=provider, mocked=mocked)
