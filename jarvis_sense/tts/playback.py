"""Reprodução de áudio via `sounddevice`, com escolha explícita de dispositivo.

`edge-tts` produz MP3; decodificamos com `av` (PyAV, já é dependência do
faster-whisper) para PCM e tocamos com `sounddevice`. Usamos `sounddevice` em
vez da API MCI (winmm) porque o MCI resolve o dispositivo de saída "padrão"
através de uma camada legada (DirectSound) que, neste ambiente, não acompanha
a troca de dispositivo padrão do Windows (ex.: conectar um headset Bluetooth)
sem reiniciar o processo — o áudio saía silenciosamente pelo alto-falante
errado. `sounddevice`/PortAudio permite escolher o dispositivo por nome,
contornando o problema (mesma solução aplicada ao microfone).

`play_file()` bloqueia até o áudio terminar — ideal para uma fala síncrona, em
que o microfone deve ficar mudo enquanto o Jarvis fala.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..core.audio_devices import resolve_device_by_name
from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger("TTS")


def _resolve_output_device(sd, name_hint: str) -> int | None:
    """Procura um dispositivo de saída cujo nome contenha `name_hint`."""
    name_hint = name_hint.strip()
    if not name_hint:
        return None
    idx = resolve_device_by_name(sd, name_hint, kind="output")
    if idx is None:
        logger.warning("Nenhum alto-falante casou com JARVIS_SPEAKER_DEVICE_NAME=%r; usando padrão.", name_hint)
    return idx


def _decode_to_pcm(path: Path) -> tuple["object", int]:
    """Decodifica o arquivo de áudio (mp3/wav) para um array numpy float32."""
    import av
    import numpy as np

    container = av.open(str(path))
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=48000)
    chunks: list[np.ndarray] = []
    stream = container.streams.audio[0]
    for frame in container.decode(stream):
        for resampled in resampler.resample(frame):
            chunks.append(resampled.to_ndarray())
    container.close()
    data = np.concatenate(chunks, axis=1).reshape(-1).astype(np.float32)
    return data, 48000


def play_file(path: str | Path) -> None:
    """Reproduz um arquivo de áudio (mp3/wav) e bloqueia até terminar."""
    path = Path(path)
    if not path.exists():
        logger.error("Arquivo de áudio inexistente: %s", path)
        return

    if not sys.platform.startswith("win"):
        logger.warning("Reprodução de áudio só testada no Windows; pulando em %s", sys.platform)
        return

    try:
        import sounddevice as sd
    except ImportError:
        logger.error("Pacote 'sounddevice' não instalado; não é possível reproduzir áudio.")
        return

    try:
        data, rate = _decode_to_pcm(path)
    except Exception as exc:  # noqa: BLE001 — decodificação pode falhar de várias formas
        logger.error("Falha ao decodificar áudio %s: %s", path, exc)
        return

    device = _resolve_output_device(sd, get_settings().speaker_device_name)
    try:
        sd.play(data, samplerate=rate, device=device, blocking=True)
    except Exception as exc:  # noqa: BLE001 — sounddevice lança erros variados
        logger.error("Falha ao tocar áudio (device=%s): %s", device, exc)
