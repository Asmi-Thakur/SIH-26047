"""Provider interfaces (Protocols).

These are the seams through which later phases add real vendors. Phase 1
defines them; mock implementations arrive with the phases that use them
(speech mock in Phase 4, LLM mock in Phase 4, OCR mock in Phase 5, FHIR mock
in Phase 7).

All protocols are intentionally narrow and vendor-agnostic.
"""
from typing import Any, Protocol


class SpeechProvider(Protocol):
    """Speech-to-text and text-to-speech."""

    async def transcribe(self, audio: bytes, *, language: str) -> str: ...

    async def synthesize(self, text: str, *, language: str) -> bytes: ...


class LLMProvider(Protocol):
    """Structured LLM calls used by dialogue/summary services.

    Implementations must return data that validates against the supplied JSON
    schema — the caller never accepts free-form model output.
    """

    async def complete_json(self, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


class OCRProvider(Protocol):
    """Document OCR: image bytes -> raw text + per-line metadata."""

    async def extract(self, image: bytes) -> dict[str, Any]: ...


class HealthRecordAdapter(Protocol):
    """Outbound health-record interoperability (FHIR/HIS/ABDM)."""

    async def create_patient(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    async def submit_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]: ...

    async def fetch_patient_records(self, external_id: str) -> list[dict[str, Any]]: ...
