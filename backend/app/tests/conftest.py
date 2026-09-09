"""Shared pytest configuration.

Environment is set before any application module is imported so tests are
predictable regardless of the developer's machine. Tests that need a database
create their own in-memory SQLite engine — no PostgreSQL is required to run
the unit suite.
"""
import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault(
    "DATABASE_URL", "sqlite+aiosqlite:///:memory:"
)
# The unit suite always exercises the deterministic OCR path; the real
# PaddleOCR engine is verified separately (docs/AI_HANDOFF.md) and through the
# provider-seam tests in test_ocr.py.
os.environ.setdefault("OCR_PROVIDER", "mock")
