"""MediKiosk backend entrypoint.

Phase 1 scope: application wiring, CORS, exception handling, router
registration and health endpoints. Business routers for later phases are
registered but return structured 501 responses.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    cases,
    documents,
    fhir,
    health,
    interview,
    llm,
    sessions,
    speech,
    triage,
)
from app.api.errors import register_exception_handlers
from app.config import get_settings
from app.db.session import engine
from app.schemas.health import HealthResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "MediKiosk — AI-assisted patient clinical intake (SIH 2026, PS 26047). "
        "Phase 1 foundation. See /docs/API_CONTRACT.md for planned endpoints."
    ),
    lifespan=lifespan,
)

# CORS: explicit allow-list only (see ARCHITECTURE.md security posture).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sih-26047.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# --- Routers (all business routers under /api) ---
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(llm.router, prefix=settings.api_prefix)
app.include_router(sessions.router, prefix=settings.api_prefix)
app.include_router(interview.router, prefix=settings.api_prefix)
app.include_router(speech.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(triage.router, prefix=settings.api_prefix)
app.include_router(cases.router, prefix=settings.api_prefix)
app.include_router(fhir.router, prefix=settings.api_prefix)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Liveness probe (no DB dependency)",
)
async def liveness() -> HealthResponse:
    """Liveness probe used by container health checks."""
    return HealthResponse(status="ok", service="medikiosk-backend")


@app.get("/", include_in_schema=False, tags=["meta"])
async def root() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
        "api_health": f"{settings.api_prefix}/health",
        "demo_mode": settings.demo_mode,
    }
