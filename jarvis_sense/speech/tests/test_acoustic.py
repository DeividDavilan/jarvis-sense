"""Testes da camada de wake word acústica: fábrica, detector nulo, e as funções
puras de parsing de modelos/caminhos e inferência de framework. O detector
openWakeWord real é validado ao vivo (precisa do modelo ONNX baixado)."""

from pathlib import Path

from jarvis_sense.core.config import Settings
from jarvis_sense.speech.acoustic import (
    NullWakeWord,
    OpenWakeWord,
    create_wake_word,
    infer_framework,
    parse_wake_models,
)


def _settings(mode: str) -> Settings:
    # Constrói Settings ignorando o .env, fixando só o modo de wake.
    s = Settings()
    object.__setattr__(s, "wake_mode", mode)
    return s


def test_parse_single_pretrained_name() -> None:
    assert parse_wake_models("hey_jarvis") == ["hey_jarvis"]


def test_parse_multiple_models() -> None:
    out = parse_wake_models("hey_jarvis, alexa")
    assert out == ["hey_jarvis", "alexa"]


def test_parse_resolves_relative_custom_path() -> None:
    root = Path("C:/proj")
    out = parse_wake_models("models/penelopo.onnx", root=root)
    assert out == [str(root / "models/penelopo.onnx")]


def test_parse_keeps_absolute_path() -> None:
    out = parse_wake_models("C:/abs/penelopo.onnx", root=Path("C:/proj"))
    assert out == [str(Path("C:/abs/penelopo.onnx"))]


def test_parse_empty_defaults_to_hey_jarvis() -> None:
    assert parse_wake_models("") == ["hey_jarvis"]


def test_parse_mixed_name_and_path() -> None:
    root = Path("C:/proj")
    out = parse_wake_models("hey_jarvis, models/penelopo.onnx", root=root)
    assert out == ["hey_jarvis", str(root / "models/penelopo.onnx")]


def test_infer_framework() -> None:
    assert infer_framework(["hey_jarvis"]) == "onnx"
    assert infer_framework(["a.onnx"]) == "onnx"
    assert infer_framework(["a.onnx", "b.tflite"]) == "tflite"


def test_factory_returns_openwakeword_for_acoustic() -> None:
    assert isinstance(create_wake_word(_settings("acoustic")), OpenWakeWord)


def test_factory_returns_null_for_text() -> None:
    assert isinstance(create_wake_word(_settings("text")), NullWakeWord)


async def test_null_never_fires() -> None:
    null = NullWakeWord()
    assert await null.is_available() is False
    assert null.process(b"\x00" * 2560) is False
    null.reset()  # não deve levantar
