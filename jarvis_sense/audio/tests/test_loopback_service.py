"""Testes do LoopbackService com fonte e STT fakes (sem WASAPI/hardware)."""

from collections.abc import AsyncIterator

from jarvis_sense.audio.services import LoopbackService
from jarvis_sense.core.config import get_settings
from jarvis_sense.core.event_types import EventName
from jarvis_sense.core.events import EventBus
from jarvis_sense.microphone.models import Utterance


class FakeLoopback:
    name = "fake-loopback"

    def __init__(self, n: int) -> None:
        self._n = n

    async def is_available(self) -> bool:
        return True

    async def utterances(self) -> AsyncIterator[Utterance]:
        for _ in range(self._n):
            yield Utterance(pcm=b"\x00\x00" * 1600, sample_rate=16000)


class FakeSTT:
    name = "fake"

    def __init__(self, text: str) -> None:
        self._text = text

    async def is_available(self) -> bool:
        return True

    async def transcribe(self, _u: Utterance) -> str:
        return self._text


async def test_publishes_audio_captured() -> None:
    bus = EventBus()
    captured: list[str] = []
    bus.subscribe(EventName.AUDIO_CAPTURED, lambda e: captured.append(e.text))

    svc = LoopbackService(
        get_settings(), bus, source=FakeLoopback(2),
        stt=FakeSTT("música tocando"), fallback_stt=FakeSTT(""),
    )
    await svc.run()

    assert captured == ["música tocando", "música tocando"]


async def test_empty_transcription_emits_nothing() -> None:
    bus = EventBus()
    captured: list[str] = []
    bus.subscribe(EventName.AUDIO_CAPTURED, lambda e: captured.append(e.text))

    svc = LoopbackService(
        get_settings(), bus, source=FakeLoopback(1),
        stt=FakeSTT("   "), fallback_stt=FakeSTT(""),
    )
    await svc.run()

    assert captured == []


async def test_unavailable_source_is_graceful() -> None:
    class Down:
        name = "down"

        async def is_available(self) -> bool:
            return False

        async def utterances(self):  # pragma: no cover - não chamado
            yield

    svc = LoopbackService(get_settings(), EventBus(), source=Down(),
                          stt=FakeSTT("x"), fallback_stt=FakeSTT(""))
    await svc.run()  # não deve levantar
