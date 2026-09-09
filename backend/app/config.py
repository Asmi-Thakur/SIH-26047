"""Application configuration.

Values are read from environment variables and an optional `.env` file in the
working directory (see `.env.example` at the repository root). Secrets are
backend-only — nothing here is ever exposed to the frontend bundle.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_env: str = "development"
    demo_mode: bool = True
    app_name: str = "MediKiosk Backend"
    app_version: str = "0.1.0"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/medikiosk"

    # --- Security ---
    session_secret: str = "replace_me"

    # --- Provider selection (all kept on the backend) ---
    llm_provider: str = "mock"
    gemini_api_key: str = ""
    speech_provider: str = "mock"
    sarvam_api_key: str = ""
    # auto = real PaddleOCR when importable, else the labelled mock;
    # "paddleocr" forces the real engine (raises if unavailable);
    # "mock" forces the honest simulated provider.
    ocr_provider: str = "auto"

    # --- Interoperability ---
    fhir_base_url: str = "http://localhost:8080/fhir"

    # --- Uploads ---
    max_upload_mb: int = 15
    upload_dir: str = "storage/uploads"

    # --- CORS: comma-separated origins allowed to call this API ---
    cors_origins: str = "http://localhost:5173"

    # --- API routing ---
    api_prefix: str = "/api"

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins parsed from the comma-separated setting."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance (module-level import safety, tests can override env)."""
    return Settings()
