"""Fonte de áudio real: microfone via `sounddevice` + segmentação por VAD.

`MicrophoneSource` implementa `IAudioSource`. Abre o microfone, lê quadros de
30 ms, passa-os ao `Segmenter` e produz `Utterance`s completas. Publica
`OnMicrophoneStarted` ao abrir o dispositivo.

`sounddevice`/`webrtcvad` são importados preguiçosamente: o módulo importa e
testa (com fontes fake) mesmo sem essas libs nativas instaladas.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from ..core.config import Settings, get_settings
from ..core.errors import AudioDeviceError
from ..core.event_types import MicrophoneStarted
from ..core.events import EventBus, get_event_bus
from ..core.logging import get_logger
from .interfaces import IAudioSource
from .models import Utterance
from .vad import FRAME_BYTES, SAMPLE_RATE, Segmenter

logger = get_logger("Speech")


class MicrophoneSource(IAudioSource):
    """Microfone real com cancelamento de ruído via VAD e detecção de silêncio."""

    name = "microphone"

    def __init__(self, settings: Settings | None = None, bus: EventBus | None = None) -> None:
        self._settings = settings or get_settings()
        self._bus = bus or get_event_bus()
        self._muted = False  # silenciado enquanto o Jarvis fala (anti-eco)

    def set_muted(self, muted: bool) -> None:
        """Silencia/religa a escuta (usado para não ouvir a própria voz)."""
        self._muted = muted

    async def is_available(self) -> bool:
        # Só o sounddevice + numpy são obrigatórios. O webrtcvad é opcional: sem
        # ele, o VAD cai para o detector por energia (puro numpy).
        try:
            import numpy  # noqa: F401
            import sounddevice  # noqa: F401
        except ImportError:
            return False
        return True

    async def frames(self) -> AsyncIterator[bytes]:
        """Fluxo primitivo: quadros PCM crus de 30 ms (16 kHz mono int16).

        Base tanto da segmentação (`utterances`) quanto da wake word acústica,
        que precisa do áudio contínuo antes de qualquer segmentação/STT.
        """
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioDeviceError("Pacote 'sounddevice' não instalado.") from exc

        queue: asyncio.Queue[bytes] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _callback(indata, _frames, _time, status) -> None:
            if status:
                logger.debug("sounddevice status: %s", status)
            if not self._muted:
                loop.call_soon_threadsafe(queue.put_nowait, bytes(indata))

        try:
            stream = sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=FRAME_BYTES // 2,  # em amostras (int16)
                dtype="int16",
                channels=1,
                callback=_callback,
            )
        except Exception as exc:  # noqa: BLE001 — sounddevice lança erros variados
            raise AudioDeviceError(f"Falha ao abrir microfone: {exc}") from exc

        with stream:
            await self._bus.publish(MicrophoneStarted(device="default"))
            logger.info("Microfone aberto (%d Hz). Ouvindo…", SAMPLE_RATE)
            while True:
                yield await queue.get()

    async def utterances(self) -> AsyncIterator[Utterance]:
        """Falas segmentadas por VAD, construídas sobre o fluxo de `frames()`."""
        segmenter = Segmenter()
        async for frame in self.frames():
            segment = segmenter.push(frame)
            if segment:
                yield Utterance(pcm=segment, sample_rate=SAMPLE_RATE)
