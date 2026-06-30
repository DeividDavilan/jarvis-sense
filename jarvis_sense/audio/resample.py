"""Conversão de áudio para o formato que o VAD/Whisper esperam: PCM mono int16 a
16 kHz.

O loopback WASAPI costuma entregar estéreo em 44.1/48 kHz (int16). Esta função
faz downmix (estéreo→mono) e reamostragem para 16 kHz por interpolação linear,
usando numpy. Lógica pura e testável (sem hardware).

`audioop` foi removido no Python 3.13+, por isso usamos numpy em vez dele.
"""

from __future__ import annotations

TARGET_RATE = 16000


def to_16k_mono(pcm: bytes, src_rate: int, channels: int) -> bytes:
    """Converte PCM int16 (`channels`, `src_rate`) em PCM mono int16 a 16 kHz."""
    if not pcm:
        return b""
    import numpy as np

    samples = np.frombuffer(pcm, dtype=np.int16)
    if channels > 1:
        # Garante comprimento múltiplo de `channels` e faz a média dos canais.
        usable = (len(samples) // channels) * channels
        samples = samples[:usable].reshape(-1, channels).mean(axis=1)
    samples = samples.astype(np.float32)

    if src_rate != TARGET_RATE and samples.size > 1:
        duration = samples.size / src_rate
        target_n = max(1, int(duration * TARGET_RATE))
        # Interpolação linear sobre uma grade temporal normalizada.
        src_x = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
        dst_x = np.linspace(0.0, 1.0, num=target_n, endpoint=False)
        samples = np.interp(dst_x, src_x, samples)

    clipped = np.clip(samples, -32768, 32767).astype(np.int16)
    return clipped.tobytes()
