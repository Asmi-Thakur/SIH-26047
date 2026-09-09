"""Health/readiness response schema."""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str | None = None
    database: str | None = None
    version: str | None = None
    demo_mode: bool | None = None
