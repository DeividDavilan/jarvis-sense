"""Adaptador STT offline: **faster-whisper** (local, gratuito).

Roda o Whisper na própria máquina (CTranslate2) — sem internet e sem chave.
Usa mais CPU/RAM (idealmente GPU), por isso é o *fallback*, não o padrão. O
modelo é carregado preguiçosamente na primeira transcrição.
"""

from __future__ import annotations

import asyncio

from ...core.config import Settings
from ...core.errors import EngineUnavailableError
from ...core.logging import get_logger
from ...microphone.models import Utterance
from ..utils import utterance_to_wav_bytes

logger = get_logger("Speech")


class FasterWhisperSTT:
    """Implementa `ISTT` via faster-whisper local."""

    name = "local"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None

    async def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return False
        return True

    def _ensure_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise EngineUnavailableError("Pacote 'faster-whisper' não instalado.") from exc
            logger.info("Carregando modelo faster-whisper '%s'…", self._settings.stt_local_model)
            self._model = WhisperModel(
                self._settings.stt_local_model,
                device="auto",
                compute_type="int8",
                download_root=self._settings.stt_local_model_dir,
            )
        return self._model

    async def transcribe(self, utterance: Utterance) -> str:
        wav = utterance_to_wav_bytes(utterance)
        return await asyncio.to_thread(self._transcribe_blocking, wav)

    def _transcribe_blocking(self, wav: bytes) -> str:
        import io

        model = self._ensure_model()
        segments, _info = model.transcribe(
            io.BytesIO(wav), language=self._settings.stt_language
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
