"""Serviço de áudio do sistema (loopback).

`LoopbackService` é um `Service` que consome a fonte de loopback, transcreve
cada trecho com o `ISTT` (Groq Whisper padrão, faster-whisper fallback) e publica
`OnAudioCaptured` no barramento. É o equivalente do `VoiceInputService`, mas para
o áudio que o computador reproduz — sem wake word (é escuta passiva).
"""

from __future__ import annotations

from ..core.config import Settings, get_settings
from ..core.errors import safe_async
from ..core.event_types import AudioCaptured, ControlCommand, EventName
from ..core.events import EventBus, get_event_bus
from ..core.logging import get_logger
from ..speech.config import create_fallback_stt, create_stt
from ..speech.interfaces import ISTT
from .capture import WasapiLoopbackSource
from .interfaces import ILoopbackSource

logger = get_logger("Audio")


class LoopbackService:
    name = "loopback-audio"

    def __init__(
        self,
        settings: Settings | None = None,
        bus: EventBus | None = None,
        source: ILoopbackSource | None = None,
        stt: ISTT | None = None,
        fallback_stt: ISTT | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._bus = bus or get_event_bus()
        self._source = source or WasapiLoopbackSource()
        self._stt = stt or create_stt(self._settings)
        self._fallback = fallback_stt or create_fallback_stt(self._settings, self._stt)
        self._active: ISTT | None = None
        self._enabled = True
        self._bus.subscribe(EventName.CONTROL_CMD, self._on_control)

    def _on_control(self, event: ControlCommand) -> None:
        if event.module != "loopback":
            return
        if event.action == "enable":
            self._enabled = True
        elif event.action == "disable":
            self._enabled = False
        else:
            self._enabled = not self._enabled
        logger.info("Loopback %s.", "habilitado" if self._enabled else "desabilitado")

    async def _resolve_stt(self) -> ISTT:
        if self._active is not None:
            return self._active
        if await self._stt.is_available():
            self._active = self._stt
        elif await self._fallback.is_available():
            self._active = self._fallback
        else:
            self._active = self._stt
        return self._active

    async def run(self) -> None:
        if not await self._source.is_available():
            logger.error(
                "Loopback WASAPI indisponível. Instale: PyAudioWPatch. "
                "Serviço de áudio do sistema inativo."
            )
            return
        logger.info("Ouvindo o áudio do sistema (loopback)…")
        async for utterance in self._source.utterances():
            await self._handle(utterance)

    @safe_async(module="Audio")
    async def _handle(self, utterance) -> None:  # noqa: ANN001
        if not self._enabled:
            return
        stt = await self._resolve_stt()
        text = (await stt.transcribe(utterance)).strip()
        if not text:
            return
        logger.info("Áudio do sistema: %r", text)
        await self._bus.publish(AudioCaptured(text=text, source="loopback"))
