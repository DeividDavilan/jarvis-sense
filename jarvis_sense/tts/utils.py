"""Utilitários do módulo TTS."""

from __future__ import annotations

import re

_WS = re.compile(r"\s+")


def clean_for_speech(text: str) -> str:
    """Normaliza texto antes de falar: colapsa espaços, remove marcações de
    código/markdown simples que soariam estranhas em voz alta."""
    if not text:
        return ""
    text = text.replace("`", "").replace("*", "").replace("#", "")
    return _WS.sub(" ", text).strip()


def rate_to_multiplier(rate: str) -> float:
    """Converte um `rate` no formato edge-tts ("+6%", "-10%") para um
    multiplicador (1.06, 0.90). Motores como o SAPI usam isso para ajustar a
    velocidade. Valores inválidos retornam 1.0."""
    try:
        pct = int(rate.strip().rstrip("%"))
        return max(0.5, min(2.0, 1.0 + pct / 100.0))
    except (ValueError, AttributeError):
        return 1.0
