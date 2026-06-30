"""Adaptador STT padrão: **Groq Whisper** (gratuito, baixíssima latência).

Envia o WAV da fala para a API do Groq (compatível com OpenAI), reaproveitando a
`GROQ_API_KEY` que o Jarvis web já usa. Quase nenhum uso de CPU/RAM local — só
precisa de internet.
"""

from __future__ import annotations

from ...core.config import Settings
from ...core.errors import EngineUnavailableError
from ...core.logging import get_logger
from ...microphone.models import Utterance
from ..utils import utterance_to_wav_bytes

logger = get_logger("Speech")


class GroqWhisperSTT:
    """Implementa `ISTT` via Groq Whisper."""

    name = "groq"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    async def is_available(self) -> bool:
        if not self._settings.has_groq:
            return False
        try:
            import groq  # noqa: F401
        except ImportError:
            return False
        return True

    def _ensure_client(self):
        if self._client is None:
            try:
                from groq import Groq
            except ImportError as exc:
                raise EngineUnavailableError("Pacote 'groq' não instalado.") from exc
            self._client = Groq(api_key=self._settings.groq_api_key)
        return self._client

    async def transcribe(self, utterance: Utterance) -> str:
        import asyncio

        if not self._settings.has_groq:
            raise EngineUnavailableError("GROQ_API_KEY ausente.")
        wav = utterance_to_wav_bytes(utterance)
        # O SDK do Groq é síncrono → roda em thread para não travar o loop async.
        return await asyncio.to_thread(self._transcribe_blocking, wav)

    def _transcribe_blocking(self, wav: bytes) -> str:
        client = self._ensure_client()
        result = client.audio.transcriptions.create(
            file=("speech.wav", wav, "audio/wav"),
            model=self._settings.stt_groq_model,
            language=self._settings.stt_language,
            response_format="text",
        )
        # response_format="text" devolve a string direta; outros formatos têm .text
        text = result if isinstance(result, str) else getattr(result, "text", "")
        return (text or "").strip()
