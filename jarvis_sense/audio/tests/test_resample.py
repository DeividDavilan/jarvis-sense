"""Testes da conversão para 16 kHz mono int16 (downmix + reamostragem)."""

import numpy as np
import pytest

from jarvis_sense.audio.resample import TARGET_RATE, to_16k_mono


def _tone(freq: float, rate: int, secs: float, channels: int = 1) -> bytes:
    t = np.linspace(0, secs, int(rate * secs), endpoint=False)
    wave = (np.sin(2 * np.pi * freq * t) * 10000).astype(np.int16)
    if channels > 1:
        wave = np.repeat(wave[:, None], channels, axis=1).flatten()
    return wave.tobytes()


def test_empty_input() -> None:
    assert to_16k_mono(b"", 48000, 2) == b""


def test_downmix_and_resample_length() -> None:
    # 1 segundo de tom estéreo a 48 kHz → ~16000 amostras mono a 16 kHz.
    pcm = _tone(440, 48000, 1.0, channels=2)
    out = to_16k_mono(pcm, 48000, 2)
    n = len(out) // 2  # int16 → 2 bytes
    assert TARGET_RATE * 0.95 <= n <= TARGET_RATE * 1.05


def test_already_16k_mono_passthrough_length() -> None:
    pcm = _tone(440, 16000, 0.5, channels=1)
    out = to_16k_mono(pcm, 16000, 1)
    assert len(out) == len(pcm)  # nada a reamostrar


def test_stereo_average_is_mono() -> None:
    # Canal esquerdo = +1000, direito = -1000 → média 0.
    left = np.full(100, 1000, dtype=np.int16)
    right = np.full(100, -1000, dtype=np.int16)
    inter = np.empty(200, dtype=np.int16)
    inter[0::2] = left
    inter[1::2] = right
    out = np.frombuffer(to_16k_mono(inter.tobytes(), 16000, 2), dtype=np.int16)
    assert np.all(np.abs(out) <= 1)  # média ≈ 0
