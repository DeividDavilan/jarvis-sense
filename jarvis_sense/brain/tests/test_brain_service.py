"""Testes da fatia vertical (BrainService) com LLM e TTS fakes — sem rede/áudio.
Valida: wake→pergunta→resposta falada; 'Jarvis' sozinho → 'Sim, senhor?';
janela de conversa; fallback de provedor; histórico de contexto."""

import time

from jarvis_sense.core.config import get_settings
from jarvis_sense.core.event_types import SpeechDetected
from jarvis_sense.core.events import EventBus
from jarvis_sense.brain.models import ChatMessage
from jarvis_sense.brain.service import BrainService


class FakeProvider:
    def __init__(self, name: str, available: bool = True, reply: str = "Claro, senhor.") -> None:
        self.name = name
        self._available = available
        self._reply = reply
        self.calls: list[list[ChatMessage]] = []

    async def is_available(self) -> bool:
        return self._available

    async def complete(self, messages: list[ChatMessage]) -> str:
        self.calls.append(messages)
        return self._reply


class FakeTTS:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    async def speak(self, text: str) -> None:
        self.spoken.append(text)


def _brain(primary, fallback=None, tts=None, bus=None):
    return BrainService(
        get_settings(),
        bus or EventBus(),
        tts=tts or FakeTTS(),
        primary=primary,
        fallback=fallback or FakeProvider("fb", available=False),
    )


async def test_wake_with_command_gets_spoken_reply() -> None:
    bus = EventBus()
    tts = FakeTTS()
    provider = FakeProvider("groq", reply="São três horas, senhor.")
    brain = _brain(provider, tts=tts, bus=bus)

    await bus.publish(SpeechDetected(text="que horas são", wake=True))

    assert tts.spoken == ["São três horas, senhor."]
    assert len(provider.calls) == 1
    # Histórico: a 1ª mensagem é sempre o system prompt do Jarvis.
    assert provider.calls[0][0].role == "system"


async def test_wake_only_confirms() -> None:
    bus = EventBus()
    tts = FakeTTS()
    brain = _brain(FakeProvider("groq"), tts=tts, bus=bus)

    await bus.publish(SpeechDetected(text="", wake=True))

    assert tts.spoken == ["Sim, senhor?"]


async def test_speech_without_wake_is_ignored_when_idle() -> None:
    bus = EventBus()
    tts = FakeTTS()
    provider = FakeProvider("groq")
    _brain(provider, tts=tts, bus=bus)

    await bus.publish(SpeechDetected(text="qualquer coisa", wake=False))

    assert tts.spoken == []
    assert provider.calls == []


async def test_conversation_window_accepts_followup_without_wake() -> None:
    bus = EventBus()
    tts = FakeTTS()
    provider = FakeProvider("groq", reply="ok")
    _brain(provider, tts=tts, bus=bus)

    await bus.publish(SpeechDetected(text="oi", wake=True))      # abre conversa
    await bus.publish(SpeechDetected(text="e agora", wake=False))  # follow-up

    assert len(provider.calls) == 2


async def test_falls_back_to_second_provider() -> None:
    bus = EventBus()
    tts = FakeTTS()
    primary = FakeProvider("groq", available=False)
    fallback = FakeProvider("anthropic", available=True, reply="via fallback")
    _brain(primary, fallback=fallback, tts=tts, bus=bus)

    await bus.publish(SpeechDetected(text="oi", wake=True))

    assert tts.spoken == ["via fallback"]


async def test_no_provider_configured_message() -> None:
    bus = EventBus()
    tts = FakeTTS()
    primary = FakeProvider("groq", available=False)
    fallback = FakeProvider("anthropic", available=False)
    _brain(primary, fallback=fallback, tts=tts, bus=bus)

    await bus.publish(SpeechDetected(text="oi", wake=True))

    assert tts.spoken and "Nenhum provedor" in tts.spoken[0]
