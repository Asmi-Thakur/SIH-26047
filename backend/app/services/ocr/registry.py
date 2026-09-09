"""OCR provider registry (OCR_PROVIDER env, default ``auto``).

Selection semantics (mirrors the speech registry pattern, ADR-016):

- ``mock``      -> the honest deterministic fixture provider (``mocked: true``).
- ``paddleocr`` -> the REAL PaddleOCR engine; raises if the paddle packages
  are not importable in this environment (never silently degrades — the caller
  decides whether to fall back to the mock and label it honestly).
- ``auto`` (default) -> PaddleOCR when importable, otherwise the labelled mock,
  so demo mode always works with zero model dependencies (spec §34/§60).

The second element of the returned tuple tells the caller whether the engine
that will actually run is a labelled simulation.
"""
from __future__ import annotations

from app.config import get_settings
from app.services.ocr.mock import MockOCRProvider


def paddle_available() -> bool:
    """True when the real engine can be imported in this environment."""
    try:
        import paddle  # noqa: F401
        import paddleocr  # noqa: F401
    except Exception:
        return False
    return True


def get_ocr_provider() -> tuple[object, bool]:
    """Return ``(provider, mocked)`` for the configured OCR_PROVIDER."""
    settings = get_settings()
    requested = (settings.ocr_provider or "auto").strip().lower()

    if requested == "mock":
        return MockOCRProvider(), True

    if requested in {"paddleocr", "auto"}:
        if paddle_available():
            from app.services.ocr.paddle import PaddleOCRProvider

            return PaddleOCRProvider(), False
        if requested == "paddleocr":
            raise RuntimeError(
                "OCR_PROVIDER=paddleocr but the paddle packages are not "
                "importable in this Python environment. Install "
                "requirements-ocr.txt in a Python 3.10–3.12 venv or set "
                "OCR_PROVIDER=mock / auto."
            )

    return MockOCRProvider(), True


__all__ = ["get_ocr_provider", "paddle_available"]
