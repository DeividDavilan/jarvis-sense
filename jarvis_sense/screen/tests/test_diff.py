"""Testes do detector de mudança de frames (lógica pura)."""

from jarvis_sense.screen.diff import FrameDiffer


def test_first_frame_is_full_change() -> None:
    d = FrameDiffer()
    assert d.diff_ratio(bytes([0] * 100)) == 1.0


def test_identical_frames_zero_change() -> None:
    d = FrameDiffer()
    sig = bytes([100] * 100)
    d.diff_ratio(sig)
    assert d.diff_ratio(sig) == 0.0


def test_partial_change_ratio() -> None:
    d = FrameDiffer(pixel_threshold=16)
    base = bytes([0] * 100)
    d.diff_ratio(base)
    # Muda 25 pixels acima do limiar (de 0 para 200).
    changed = bytes([200] * 25 + [0] * 75)
    assert d.diff_ratio(changed) == 0.25


def test_below_threshold_not_counted() -> None:
    d = FrameDiffer(pixel_threshold=16)
    d.diff_ratio(bytes([100] * 100))
    # Variação de 10 (< 16) não conta como mudança.
    assert d.diff_ratio(bytes([110] * 100)) == 0.0


def test_size_change_is_full_change() -> None:
    d = FrameDiffer()
    d.diff_ratio(bytes([0] * 100))
    assert d.diff_ratio(bytes([0] * 50)) == 1.0
