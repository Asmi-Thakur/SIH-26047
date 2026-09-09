"""Shared response shapes used across the API.

Errors use the envelope documented in docs/API_CONTRACT.md:
``{"detail": {"status": "error", "code": ..., "message": ...}}``
"""
from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    status: str = "error"
    code: str
    message: str
    errors: list[Any] | None = None


class NotImplementedDetail(BaseModel):
    status: str = "not_implemented"
    feature: str
    phase: int
    message: str
