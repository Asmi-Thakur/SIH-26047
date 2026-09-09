"""Speech provider registry (SPEECH_PROVIDER env, default ``mock``).

Add real vendors here behind the same SpeechProvider protocol; never branch
on the vendor inside routers. ``mocked`` is reported on every response so the
UI/demo can label simulated transcription honestly.
"""
from app.config import get_settings
from app.services.speech.mock import MockSpeechProvider


def get_speech_provider():
    """Return the configured provider instance.

    Only ``mock`` is implemented so far. Setting SPEECH_PROVIDER to a real
    vendor (e.g. ``sarvam``) raises until that vendor's provider lands.
    """
    settings = get_settings()
    if settings.speech_provider == "mock":
        return MockSpeechProvider(), True
    raise NotImplementedError(
        f"Speech provider '{settings.speech_provider}' is not implemented yet; "
        "use SPEECH_PROVIDER=mock (demo) or implement the vendor provider."
    )
