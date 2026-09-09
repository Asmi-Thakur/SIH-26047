"""Configuration loading tests (pydantic-settings)."""
from app.config import Settings


def test_defaults_are_safe() -> None:
    # Constructed explicitly so the suite-level env (APP_ENV=test in conftest)
    # cannot leak in; the point is that defaults are demo-safe.
    settings = Settings(_env_file=None, app_env="development", demo_mode=True)
    assert settings.app_env == "development"
    assert settings.demo_mode is True
    assert settings.session_secret == "replace_me"  # never a real default
    assert settings.llm_provider == "mock"
    assert settings.speech_provider == "mock"
    assert settings.max_upload_mb == 15


def test_cors_origin_list_parsing() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins="http://localhost:5173, http://192.168.1.10:5173 ,",
    )
    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "http://192.168.1.10:5173",
    ]


def test_env_values_override_defaults() -> None:
    settings = Settings(_env_file=None, demo_mode=False, max_upload_mb=30)
    assert settings.demo_mode is False
    assert settings.max_upload_mb == 30
    assert settings.max_upload_bytes == 30 * 1024 * 1024
