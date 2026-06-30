"""Testes do barramento de eventos: entrega por tópico, assinatura global,
desinscrição e isolamento de erros (um handler que falha não derruba os outros).
"""

import pytest

from jarvis_sense.core.event_types import EventName, OCRFinished, SpeechDetected
from jarvis_sense.core.events import EventBus


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


async def test_topic_delivery(bus: EventBus) -> None:
    received: list[str] = []
    bus.subscribe(EventName.SPEECH_DETECTED, lambda e: received.append(e.text))

    await bus.publish(SpeechDetected(text="olá"))
    await bus.publish(OCRFinished(text="ignorar"))  # tópico diferente

    assert received == ["olá"]


async def test_subscribe_all_receives_everything(bus: EventBus) -> None:
    seen: list[str] = []
    bus.subscribe_all(lambda e: seen.append(e.name.value))

    await bus.publish(SpeechDetected(text="a"))
    await bus.publish(OCRFinished(text="b"))

    assert seen == [EventName.SPEECH_DETECTED.value, EventName.OCR_FINISHED.value]


async def test_async_handler(bus: EventBus) -> None:
    received: list[str] = []

    async def handler(e) -> None:
        received.append(e.text)

    bus.subscribe(EventName.SPEECH_DETECTED, handler)
    await bus.publish(SpeechDetected(text="async"))

    assert received == ["async"]


async def test_unsubscribe(bus: EventBus) -> None:
    received: list[str] = []
    off = bus.subscribe(EventName.SPEECH_DETECTED, lambda e: received.append(e.text))

    await bus.publish(SpeechDetected(text="um"))
    off()
    await bus.publish(SpeechDetected(text="dois"))

    assert received == ["um"]


async def test_failing_handler_is_isolated(bus: EventBus) -> None:
    received: list[str] = []

    def boom(_e) -> None:
        raise RuntimeError("falha proposital")

    bus.subscribe(EventName.SPEECH_DETECTED, boom)
    bus.subscribe(EventName.SPEECH_DETECTED, lambda e: received.append(e.text))

    # Não deve levantar — o erro do primeiro handler é isolado e logado.
    await bus.publish(SpeechDetected(text="sobrevivi"))

    assert received == ["sobrevivi"]
