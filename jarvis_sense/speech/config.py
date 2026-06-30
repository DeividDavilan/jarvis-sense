"""Fábrica de motores STT, com seleção híbrida (Groq padrão + faster-whisper)."""

from __future__ import annotations

from ..core.config import Settings
from .adapters.faster_whisper import FasterWhisperSTT
from .adapters.groq_whisper import GroqWhisperSTT
from .interfaces import ISTT


def create_stt(settings: Settings, *, engine: str | None = None) -> ISTT:
    """Cria o motor STT primário conforme a config (`engine` força a escolha)."""
    choice = (engine or settings.stt_engine).lower()
    if choice == "local":
        return FasterWhisperSTT(settings)
    return GroqWhisperSTT(settings)


def create_fallback_stt(settings: Settings, primary: ISTT) -> ISTT:
    """O fallback é sempre o "outro" motor: se o primário é Groq (online), o
    fallback é o local (offline), e vice-versa."""
    if primary.name == "groq":
        return FasterWhisperSTT(settings)
    return GroqWhisperSTT(settings)
