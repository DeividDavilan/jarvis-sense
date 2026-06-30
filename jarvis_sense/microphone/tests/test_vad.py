"""Testes da segmentação por VAD usando o detector por energia (numpy, sem
dependência nativa). Valida que fala (alta energia) seguida de silêncio produz
um segmento, e que silêncio puro não produz nada."""

import numpy as np

from jarvis_sense.microphone.vad import FRAME_BYTES, Segmenter, _EnergyDetector


def _frame(amplitude: int) -> bytes:
    n = FRAME_BYTES // 2
    return (np.full(n, amplitude, dtype=np.int16)).tobytes()


def _silence() -> bytes:
    return _frame(0)


def _loud() -> bytes:
    return _frame(8000)


def test_energy_detector_distinguishes_loud_from_silence() -> None:
    det = _EnergyDetector()
    assert det.is_speech(_loud()) is True
    # Vários silêncios seguidos continuam como não-fala.
    assert det.is_speech(_silence()) is False


def test_segmenter_emits_after_speech_then_silence() -> None:
    # Força o detector por energia (não depende de webrtcvad estar instalado).
    seg = Segmenter(silence_ms=90, min_speech_ms=30)
    seg._detector = _EnergyDetector()

    out = None
    # ~300 ms de fala…
    for _ in range(10):
        assert seg.push(_loud()) is None
    # …seguidos de silêncio suficiente para fechar o segmento (3 quadros = 90 ms).
    for _ in range(3):
        res = seg.push(_silence())
        out = out or res

    assert out is not None
    assert len(out) > FRAME_BYTES  # contém vários quadros de fala


def test_segmenter_ignores_pure_silence() -> None:
    seg = Segmenter(silence_ms=90, min_speech_ms=30)
    seg._detector = _EnergyDetector()
    for _ in range(20):
        assert seg.push(_silence()) is None


def test_wrong_frame_size_ignored() -> None:
    seg = Segmenter()
    seg._detector = _EnergyDetector()
    assert seg.push(b"\x00\x00") is None  # tamanho errado → ignorado
