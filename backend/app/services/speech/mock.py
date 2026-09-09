"""Mock speech provider (DEMO_MODE / SPEECH_PROVIDER=mock).

Implements the ``SpeechProvider`` protocol so the full audio pipeline
(capture -> upload -> endpoint -> transcript -> audio out) can run with zero
external dependencies. Transcription returns a deterministic bilingual sample
(real ASR vendors replace this class — see docs/AI_HANDOFF.md).
"""
import struct

# Sample "reply" that matches the demo narrative (chest pain + dyspnea).
SAMPLE_EN = (
    "I have had chest pain for three days and I also feel short of breath."
)
SAMPLE_HI = (
    "मुझे तीन दिन से सीने में दर्द है और सांस लेने में भी तकलीफ हो रही है।"
)


def silence_wav(seconds: float = 0.4, rate: int = 8000) -> bytes:
    """A tiny valid 16-bit mono PCM WAV of silence (plays in any browser)."""
    data_size = int(rate * seconds) * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,          # PCM
        1,          # mono
        rate,
        rate * 2,   # byte rate
        2,          # block align
        16,         # bits per sample
        b"data",
        data_size,
    )
    return header + b"\x00\x00" * (data_size // 2)


class MockSpeechProvider:
    """Deterministic mock of the SpeechProvider protocol."""

    name = "mock"

    async def transcribe(self, audio: bytes, *, language: str) -> str:
        # audio is intentionally ignored: a real provider would consume it.
        if language and language.lower().startswith("hi"):
            return SAMPLE_HI
        return SAMPLE_EN

    async def synthesize(self, text: str, *, language: str) -> bytes:
        return silence_wav()
