"""Modelos de dados do módulo TTS."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VoiceConfig:
    """Parâmetros de uma voz TTS.

    `voice` é o identificador específico do motor (ex.: "pt-BR-AntonioNeural"
    no edge-tts). `rate` segue o formato do edge-tts ("+6%", "-10%"); motores
    que não suportam porcentagem traduzem para sua própria escala.
    """

    voice: str = "pt-BR-AntonioNeural"
    rate: str = "+6%"
    language: str = "pt-BR"
