"""Testes do detector de wake word (textual, com normalização de acentos)."""

from jarvis_sense.speech.wake_word import WakeWordDetector


def test_detects_and_extracts_command() -> None:
    det = WakeWordDetector("jarvis")
    found, command = det.detect("Jarvis, que horas são?")
    assert found is True
    assert command == "que horas são?"


def test_detects_with_accent_and_case() -> None:
    det = WakeWordDetector("jarvis")
    found, command = det.detect("JÁRVIS abrir o painel")
    assert found is True
    assert command == "abrir o painel"


def test_wake_word_only_returns_empty_command() -> None:
    det = WakeWordDetector("jarvis")
    found, command = det.detect("Jarvis")
    assert found is True
    assert command == ""


def test_no_wake_word() -> None:
    det = WakeWordDetector("jarvis")
    found, command = det.detect("abrir o navegador")
    assert found is False
    assert command == ""
