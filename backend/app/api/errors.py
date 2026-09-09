"""Structured error handling.

- ``not_implemented(...)``: helper used by routers whose features land in a
  later phase. Returns a 501 with a machine-readable body.
- ``register_exception_handlers(app)``: wires validation + unexpected-error
  handlers so clients always receive the documented error envelope.
"""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("medikiosk")


def not_implemented(feature: str, phase: int) -> HTTPException:
    """Build the 501 response for a deferred feature."""
    return HTTPException(
        status_code=501,
        detail={
            "status": "not_implemented",
            "feature": feature,
            "phase": phase,
            "message": f"Planned for Phase {phase}. See docs/API_CONTRACT.md.",
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach structured handlers for validation and unexpected errors."""

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "status": "error",
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "errors": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Never log clinical payloads; log routing context only.
        logger.exception(
            "Unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "status": "error",
                    "code": "internal_error",
                    "message": "Internal server error",
                }
            },
        )
