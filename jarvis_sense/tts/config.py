"""Configuração do módulo TTS, derivada das `Settings` globais."""

from __future__ import annotations

from ..core.config import Settings
from .models import VoiceConfig


def voice_config_from_settings(settings: Settings) -> VoiceConfig:
    return VoiceConfig(voice=settings.tts_voice, rate=settings.tts_rate)
