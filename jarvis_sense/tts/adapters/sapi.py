"""Adaptador TTS offline: **SAPI / System.Speech do Windows**.

Não exige nenhum pacote Python: usa o `System.Speech.Synthesis.SpeechSynthesizer`
do .NET, já presente em qualquer Windows, acionado via PowerShell. Serve de
fallback quando o edge-tts não está disponível (ex.: sem internet). 100% offline.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys

from ...core.logging import get_logger
from ..models import VoiceConfig
from ..utils import clean_for_speech, rate_to_multiplier

logger = get_logger("TTS")


class SapiTTS:
    """Implementa `ITTS` usando System.Speech via PowerShell."""

    name = "sapi"

    def __init__(self, config: VoiceConfig) -> None:
        self._config = config

    async def is_available(self) -> bool:
        return sys.platform.startswith("win")

    async def speak(self, text: str) -> None:
        text = clean_for_speech(text)
        if not text or not sys.platform.startswith("win"):
            return
        await asyncio.to_thread(self._speak_blocking, text)

    def _speak_blocking(self, text: str) -> None:
        # System.Speech Rate vai de -10 a +10. Mapeamos o multiplicador (~0.5..2.0)
        # para essa faixa: 1.0 → 0; 1.5 → +5; 0.5 → -5.
        mult = rate_to_multiplier(self._config.rate)
        rate = max(-10, min(10, round((mult - 1.0) * 10)))
        safe_text = text.replace("'", "''")  # escapa aspas simples p/ PowerShell
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = {rate}; "
            # Tenta selecionar uma voz pt-BR, se houver.
            "try { $s.SelectVoiceByHints('NotSet','NotSet',0,[System.Globalization.CultureInfo]'pt-BR') } catch {}; "
            f"$s.Speak('{safe_text}')"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.error("Falha no SAPI/PowerShell: %s", exc)
