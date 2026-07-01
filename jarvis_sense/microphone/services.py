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

from ..core.audio_devices import resolve_device_by_name
from ..core.config import Settings, get_settings
from ..core.errors import AudioDeviceError
from ..core.event_types import MicrophoneStarted
from ..core.events import EventBus, get_event_bus
from ..core.logging import get_logger
from .interfaces import IAudioSource
from .models import Utterance
from .vad import FRAME_BYTES, SAMPLE_RATE, Segmenter

logger = get_logger("Speech")


def _apply_gain(pcm: bytes, gain: float) -> bytes:
    """Multiplica o PCM int16 por `gain`, saturando (clip) nos limites de 16 bits."""
    import numpy as np

    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) * gain
    return np.clip(samples, -32768, 32767).astype(np.int16).tobytes()


class MicrophoneSource(IAudioSource):
    """Microfone real com cancelamento de ruído via VAD e detecção de silêncio."""

    name = "microphone"

    def __init__(self, settings: Settings | None = None, bus: EventBus | None = None) -> None:
        self._settings = settings or get_settings()
        self._bus = bus or get_event_bus()
        self._muted = False  # silenciado enquanto o Jarvis fala (anti-eco)
        self._stream = None  # stream ativa (sounddevice.RawInputStream), se aberta
        self._sd = None
        self._device: int | None = None
        self._callback = None

    def set_muted(self, muted: bool) -> None:
        """Silencia/religa a escuta (usado para não ouvir a própria voz).

        Em headsets Bluetooth, manter o stream de entrada aberto trava o link
        no perfil HFP (mono, viva-voz) — o que impede o próprio headset de
        tocar áudio de saída em boa qualidade (perfil A2DP) ao mesmo tempo.
        Por isso, além de descartar os quadros, fechamos e reabrimos o stream
        de verdade: isso solta o perfil Bluetooth enquanto o Jarvis fala e o
        Windows consegue trocar para A2DP até a próxima vez que ouvirmos.
        """
        self._muted = muted
        if self._sd is None or self._callback is None:
            return  # frames() ainda não abriu nada
        try:
            if muted and self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None
                logger.debug("Microfone fechado (Jarvis falando) — libera o Bluetooth para áudio.")
            elif not muted and self._stream is None:
                self._stream = self._open_stream(self._sd, self._callback, self._device)
                logger.debug("Microfone reaberto (%s).", "device=" + str(self._device))
        except Exception as exc:  # noqa: BLE001 — sounddevice/PortAudio lança erros variados
            logger.warning("Falha ao pausar/retomar o microfone: %s", exc)

    def _open_stream(self, sd, callback, device: int | None):
        stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=FRAME_BYTES // 2,  # em amostras (int16)
            dtype="int16",
            channels=1,
            device=device,
            callback=callback,
        )
        stream.start()
        return stream

    async def is_available(self) -> bool:
        # Só o sounddevice + numpy são obrigatórios. O webrtcvad é opcional: sem
        # ele, o VAD cai para o detector por energia (puro numpy).
        try:
            import numpy  # noqa: F401
            import sounddevice  # noqa: F401
        except ImportError:
            return False
        return True

    def _resolve_device(self, sd) -> int | None:
        """Resolve o índice do dispositivo de entrada a usar.

        Se `JARVIS_MIC_DEVICE_NAME` estiver configurado, procura por um
        dispositivo de entrada cujo nome contenha esse trecho (o PortAudio
        pode não refletir o padrão atual do Windows — ver comentário do
        setting). Sem configuração, retorna `None` (padrão do sistema).
        """
        name_hint = self._settings.mic_device_name.strip()
        if not name_hint:
            return None
        idx = resolve_device_by_name(sd, name_hint, kind="input")
        if idx is None:
            logger.warning("Nenhum microfone casou com JARVIS_MIC_DEVICE_NAME=%r; usando padrão.", name_hint)
            return None
        logger.info("Microfone selecionado por nome (%r): [%d] %s", name_hint, idx, sd.query_devices()[idx]["name"])
        return idx

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
        gain = self._settings.mic_gain

        def _callback(indata, _frames, _time, status) -> None:
            if status:
                logger.debug("sounddevice status: %s", status)
            frame = _apply_gain(bytes(indata), gain) if gain != 1.0 else bytes(indata)
            loop.call_soon_threadsafe(queue.put_nowait, frame)

        device = self._resolve_device(sd)
        self._sd = sd
        self._callback = _callback
        self._device = device
        try:
            self._stream = self._open_stream(sd, _callback, device)
        except Exception as exc:  # noqa: BLE001 — sounddevice lança erros variados
            raise AudioDeviceError(f"Falha ao abrir microfone: {exc}") from exc

        try:
            await self._bus.publish(MicrophoneStarted(device=str(device) if device is not None else "default"))
            logger.info("Microfone aberto (%d Hz, device=%s). Ouvindo…", SAMPLE_RATE, device)
            while True:
                yield await queue.get()
        finally:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None

    async def utterances(self) -> AsyncIterator[Utterance]:
        """Falas segmentadas por VAD, construídas sobre o fluxo de `frames()`."""
        segmenter = Segmenter()
        async for frame in self.frames():
            segment = segmenter.push(frame)
            if segment:
                yield Utterance(pcm=segment, sample_rate=SAMPLE_RATE)
