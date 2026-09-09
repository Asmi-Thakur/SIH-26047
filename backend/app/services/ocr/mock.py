"""Honest mock OCR provider (DEMO_MODE default).

Deterministic, labelled simulation — it NEVER reads the uploaded bytes and
NEVER claims to be real OCR. It returns the text a clean printed demo lab
report would contain so the downstream classification/extraction/case
pipeline can be demonstrated end-to-end with zero model dependencies
(spec §34, §60). Every result carries ``mocked: true`` and the API surfaces
it so demo truth is never overstated.
"""
from __future__ import annotations


class MockOCRProvider:
    """Deterministic fixture provider (labelled ``mocked: true``)."""

    name = "mock"
    mocked = True

    async def extract(self, image: bytes, mime_type: str | None = None) -> dict:
        # Deliberately ignores ``image`` — this is a simulation, not OCR.
        return {
            "pages": [
                {
                    "page_number": 1,
                    "lines": [
                        "Demo Diagnostics Laboratory",
                        "Patient: Demo Patient   Date: 2026-08-28",
                        "Glucose 145 mg/dL (Ref 70-140) HIGH",
                        "Haemoglobin 13.5 g/dL (Ref 13-17)",
                        "Creatinine 1.1 mg/dL (Ref 0.7-1.3)",
                    ],
                }
            ],
            "page_count": 1,
            "text": (
                "Demo Diagnostics Laboratory\n"
                "Patient: Demo Patient   Date: 2026-08-28\n"
                "Glucose 145 mg/dL (Ref 70-140) HIGH\n"
                "Haemoglobin 13.5 g/dL (Ref 13-17)\n"
                "Creatinine 1.1 mg/dL (Ref 0.7-1.3)"
            ),
            "confidence": 0.99,
            "provider": self.name,
            "mocked": True,
        }


__all__ = ["MockOCRProvider"]
