"""Testes do despacho de tarefas por voz: parsing dos gatilhos e fluxo completo
(comando de voz → JarvisClient.dispatch) com cliente fake."""

from jarvis_sense.bridge.dispatch import TaskDispatchService
from jarvis_sense.core.config import get_settings
from jarvis_sense.core.event_types import SpeechDetected
from jarvis_sense.core.events import EventBus


def test_parse_title_variants() -> None:
    p = TaskDispatchService.parse_title
    assert p("criar tarefa revisar o contrato") == "revisar o contrato"
    assert p("nova tarefa: ligar para o cliente") == "ligar para o cliente"
    assert p("anota uma tarefa de pagar o boleto") == "pagar o boleto"
    assert p("adicionar tarefa pra comprar café.") == "comprar café"


def test_parse_title_ignores_non_task() -> None:
    p = TaskDispatchService.parse_title
    assert p("que horas são") is None
    assert p("abrir o navegador") is None


class FakeClient:
    def __init__(self) -> None:
        self.dispatched: list[str] = []

    async def dispatch(self, title: str, agent_name=None):
        self.dispatched.append(title)
        return {"id": "t1", "title": title}


class FakeTTS:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    async def speak(self, text: str) -> None:
        self.spoken.append(text)


async def test_voice_command_dispatches_task() -> None:
    bus = EventBus()
    client = FakeClient()
    tts = FakeTTS()
    TaskDispatchService(get_settings(), bus, client=client, tts=tts)

    await bus.publish(SpeechDetected(text="criar tarefa revisar a proposta", wake=True))

    assert client.dispatched == ["revisar a proposta"]
    assert tts.spoken and "Tarefa criada" in tts.spoken[0]


async def test_non_task_speech_is_ignored() -> None:
    bus = EventBus()
    client = FakeClient()
    TaskDispatchService(get_settings(), bus, client=client)

    await bus.publish(SpeechDetected(text="qual a previsão do tempo", wake=True))

    assert client.dispatched == []
