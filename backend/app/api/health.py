"""Health / readiness endpoints (mounted under /api)."""
from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import AppSettings, DbSession
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


# @router.get("", response_model=HealthResponse, summary="API readiness incl. DB ping")
# async def api_health(session: DbSession, settings: AppSettings) -> HealthResponse:
#     """Readiness probe.

#     The endpoint reports the database state but stays healthy even when the
#     database is unreachable, so the liveness of the API is never confused with
#     the state of the database.
#     """
#     database = "ok"
#     try:
#         await session.execute(text("SELECT 1"))
#     except Exception:  # pragma: no cover - exercised only when DB is down
#         database = "unavailable"

#     return HealthResponse(
#         status="ok",
#         service="medikiosk-backend",
#         environment=settings.app_env,
#         database=database,
#         version=settings.app_version,
#         demo_mode=settings.demo_mode,
#     )

@router.get("", response_model=HealthResponse, summary="API readiness incl. DB ping")
async def api_health(session: DbSession, settings: AppSettings) -> HealthResponse:
    database = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        database = f"unavailable: {type(exc).__name__} ({exc})"

    return HealthResponse(
        status="ok",
        service="medikiosk-backend",
        environment=settings.app_env,
        database=database,
        version=settings.app_version,
        demo_mode=settings.demo_mode,
    )