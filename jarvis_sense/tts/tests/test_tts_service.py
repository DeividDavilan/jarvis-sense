"""Testes do TTSService: fallback automático, eventos de fala e utilitários.
Usa motores fake — não toca áudio real."""

import pytest

from jarvis_sense.core.config import get_settings
from jarvis_sense.core.event_types import EventName
from jarvis_sense.core.events import EventBus
from jarvis_sense.tts.services import TTSService, create_tts
from jarvis_sense.tts.utils import clean_for_speech, rate_to_multiplier


class FakeTTS:
    """Motor falso que registra o que foi falado."""

    def __init__(self, name: str, available: bool = True) -> None:
        self.name = name
        self._available = available
        self.spoken: list[str] = []

    async def is_available(self) -> bool:
        return self._available

    async def speak(self, text: str) -> None:
        self.spoken.append(text)


def test_clean_for_speech_strips_markup() -> None:
    assert clean_for_speech("  **oi**  `code`  ") == "oi code"
    assert clean_for_speech("") == ""


def test_rate_to_multiplier() -> None:
    assert rate_to_multiplier("+6%") == pytest.approx(1.06)
    assert rate_to_multiplier("-10%") == pytest.approx(0.90)
    assert rate_to_multiplier("lixo") == 1.0


def test_create_tts_unknown_falls_back_to_edge() -> None:
    engine = create_tts(get_settings(), engine="inexistente")
    assert engine.name == "edge"


async def test_uses_primary_when_available() -> None:
    primary = FakeTTS("primary", available=True)
    fallback = FakeTTS("fallback")
    svc = TTSService(get_settings(), EventBus(), primary=primary, fallback=fallback)

    await svc.speak("olá")

    assert primary.spoken == ["olá"]
    assert fallback.spoken == []


async def test_falls_back_when_primary_unavailable() -> None:
    primary = FakeTTS("primary", available=False)
    fallback = FakeTTS("fallback", available=True)
    svc = TTSService(get_settings(), EventBus(), primary=primary, fallback=fallback)

    await svc.speak("olá")

    assert primary.spoken == []
    assert fallback.spoken == ["olá"]


async def test_emits_speaking_events_around_speech() -> None:
    bus = EventBus()
    flags: list[bool] = []
    bus.subscribe(EventName.JARVIS_SPEAKING, lambda e: flags.append(e.speaking))

    svc = TTSService(get_settings(), bus, primary=FakeTTS("p"), fallback=FakeTTS("f"))
    await svc.speak("teste")

    assert flags == [True, False]  # começou a falar, depois parou


async def test_empty_text_is_noop() -> None:
    primary = FakeTTS("primary")
    svc = TTSService(get_settings(), EventBus(), primary=primary, fallback=FakeTTS("f"))
    await svc.speak("   ")
    assert primary.spoken == []
