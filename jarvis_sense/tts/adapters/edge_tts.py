"""Adaptador TTS padrão: **edge-tts** (vozes neurais da Microsoft, gratuitas e
online). Sintetiza para um MP3 temporário e reproduz via MCI nativo do Windows.

Requer o pacote `edge-tts` (em requirements.txt). Se ausente, `is_available()`
retorna False e o serviço cai para o motor offline (SAPI).
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from ...core.errors import EngineUnavailableError
from ...core.logging import get_logger
from ..models import VoiceConfig
from ..playback import play_file
from ..utils import clean_for_speech

logger = get_logger("TTS")


class EdgeTTS:
    """Implementa `ITTS` usando edge-tts."""

    name = "edge"

    def __init__(self, config: VoiceConfig) -> None:
        self._config = config

    async def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False
        return True

    async def speak(self, text: str) -> None:
        text = clean_for_speech(text)
        if not text:
            return
        try:
            import edge_tts
        except ImportError as exc:
            raise EngineUnavailableError("Pacote 'edge-tts' não instalado.") from exc

        communicate = edge_tts.Communicate(
            text, voice=self._config.voice, rate=self._config.rate
        )

        # Escreve o MP3 num arquivo temporário e reproduz (a síntese é online).
        tmp = Path(tempfile.gettempdir()) / f"jarvis_tts_{abs(hash(text)) % 10_000}.mp3"
        await communicate.save(str(tmp))

        # A reprodução é bloqueante (MCI) → roda em thread para não travar o loop.
        await asyncio.to_thread(play_file, tmp)

        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
