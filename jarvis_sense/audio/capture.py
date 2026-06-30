"""Fonte de loopback real via **PyAudioWPatch** (WASAPI loopback no Windows).

Abre o dispositivo de loopback do alto-falante padrão, lê blocos de áudio,
converte para 16 kHz mono int16 (`resample.to_16k_mono`) e segmenta a fala com
o mesmo `Segmenter` (VAD) do microfone, produzindo `Utterance`s.

`pyaudiowpatch` precisa do PortAudio (vem no wheel) e é importado
preguiçosamente — sem ele, `is_available()` é False e o serviço fica inativo.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from ..core.errors import AudioDeviceError
from ..core.logging import get_logger
from ..microphone.models import Utterance
from ..microphone.vad import FRAME_BYTES, Segmenter
from .resample import TARGET_RATE, to_16k_mono

logger = get_logger("Audio")

# Bloco de leitura do loopback (~100 ms na taxa nativa); resampleado depois.
_READ_FRAMES = 4096


class WasapiLoopbackSource:
    name = "loopback"

    async def is_available(self) -> bool:
        try:
            import pyaudiowpatch  # noqa: F401
        except ImportError:
            return False
        return True

    async def utterances(self) -> AsyncIterator[Utterance]:
        try:
            import pyaudiowpatch as pyaudio
        except ImportError as exc:
            raise AudioDeviceError("Pacote 'PyAudioWPatch' não instalado.") from exc

        queue: asyncio.Queue[bytes] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        pa = pyaudio.PyAudio()

        try:
            device = pa.get_default_wasapi_loopback()
        except Exception as exc:  # noqa: BLE001
            pa.terminate()
            raise AudioDeviceError(f"Loopback WASAPI indisponível: {exc}") from exc

        src_rate = int(device["defaultSampleRate"])
        channels = int(device["maxInputChannels"]) or 2

        def _callback(in_data, _frame_count, _time_info, _status):
            loop.call_soon_threadsafe(queue.put_nowait, in_data)
            return (None, pyaudio.paContinue)

        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=src_rate,
                frames_per_buffer=_READ_FRAMES,
                input=True,
                input_device_index=device["index"],
                stream_callback=_callback,
            )
        except Exception as exc:  # noqa: BLE001
            pa.terminate()
            raise AudioDeviceError(f"Falha ao abrir loopback: {exc}") from exc

        logger.info(
            "Loopback aberto: '%s' (%d Hz, %d ch) → 16k mono.",
            device.get("name", "?"),
            src_rate,
            channels,
        )

        segmenter = Segmenter()
        carry = b""  # sobra de bytes que não completou um quadro de 30 ms
        try:
            while True:
                block = await queue.get()
                pcm16k = to_16k_mono(block, src_rate, channels)
                carry += pcm16k
                # Alimenta o VAD em quadros exatos de FRAME_BYTES.
                while len(carry) >= FRAME_BYTES:
                    frame, carry = carry[:FRAME_BYTES], carry[FRAME_BYTES:]
                    segment = segmenter.push(frame)
                    if segment:
                        yield Utterance(pcm=segment, sample_rate=TARGET_RATE)
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
