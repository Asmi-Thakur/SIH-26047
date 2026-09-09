"""Clinical extraction service (Phase 3d/2).

Provider selection mirrors speech (ADR-016 style):

- ``LLM_PROVIDER=mock`` (default): deterministic keyword extractor.
- ``LLM_PROVIDER=gemini`` with a ``GEMINI_API_KEY``: REST call asking for
  strict JSON against the same shape; if the response is malformed or the
  call fails, we fall back to the deterministic extractor and label the
  result ``mocked: true`` so demo truth is never overstated.

Output is always a *structured extraction* (never a diagnosis): the
physician remains the decision-maker.
"""
import json

import httpx

from app.config import Settings
from app.services.llm.mock_extractor import extract_fields

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)

SYSTEM_SHAPE = """Return ONLY JSON with keys:
complaint (array), duration (string|null), conditions (array),
medications (array), missing_information (array of strings).
No prose around the JSON. This is a history extractor, not a diagnosis."""


async def _gemini_extract(text: str, api_key: str) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": f"{SYSTEM_SHAPE}\n\nPatient: {text}"}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0,
                },
            },
        )
        response.raise_for_status()
        body = response.json()
    raw = (
        body["candidates"][0]["content"]["parts"][0]["text"]
        if body.get("candidates")
        else None
    )
    if not raw:
        raise ValueError("Gemini returned no content")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Gemini returned non-object JSON")
    # Ensure every contract key exists before the caller accepts the output.
    for key in ("complaint", "duration", "conditions", "medications", "missing_information"):
        parsed.setdefault(key, None if key == "duration" else [])
    return parsed


async def run_extraction(
    text: str, language: str, settings: Settings
) -> tuple[dict, str, bool]:
    """Return (fields, provider_name, mocked) for the given free text."""
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        try:
            fields = await _gemini_extract(text, settings.gemini_api_key)
            return fields, "gemini", False
        except Exception:
            # Fall back silently to the deterministic extractor.
            pass
    return extract_fields(text), "mock", True
