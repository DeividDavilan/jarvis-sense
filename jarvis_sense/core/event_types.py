"""Tipos de evento que trafegam no barramento (`core.events.EventBus`).

São o "contrato" entre os módulos: um módulo publica um evento e nunca chama
outro módulo diretamente (Inversão de Dependência / baixo acoplamento). Os
nomes espelham 1:1 os eventos pedidos no prompt.

Cada evento é uma `dataclass` imutável (frozen). O campo de classe `name`
(`ClassVar`) carrega o nome canônico — usado como tópico no barramento e como
`type` no payload enviado pela ponte WebSocket. `to_payload()` serializa o
evento para um dicionário JSON-friendly.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, ClassVar


class EventName(str, Enum):
    """Nomes canônicos dos eventos (tópicos do barramento)."""

    MIC_STARTED = "OnMicrophoneStarted"
    SPEECH_DETECTED = "OnSpeechDetected"
    AUDIO_CAPTURED = "OnAudioCaptured"
    SCREEN_CHANGED = "OnScreenChanged"
    OCR_FINISHED = "OnOCRFinished"
    VISION_UPDATED = "OnVisionUpdated"
    JARVIS_SPEAKING = "OnJarvisSpeaking"
    MIC_STATE = "OnMicState"
    CONTROL_CMD = "OnControlCommand"
    BRAIN_THINKING = "OnBrainThinking"


@dataclass(frozen=True, slots=True)
class Event:
    """Base de todos os eventos.

    `ts` é o epoch (segundos). `name` é um `ClassVar` definido por subclasse,
    portanto não entra no `__init__` nem no `asdict`.
    """

    name: ClassVar[EventName]
    ts: float = field(default_factory=time.time)

    def to_payload(self) -> dict[str, Any]:
        """Dicionário JSON-friendly: `{type, ...campos}` para a ponte/WS."""
        data = asdict(self)
        data["type"] = self.name.value
        return data


@dataclass(frozen=True, slots=True)
class MicrophoneStarted(Event):
    name: ClassVar[EventName] = EventName.MIC_STARTED
    device: str = ""


@dataclass(frozen=True, slots=True)
class SpeechDetected(Event):
    """Fala do usuário transcrita pelo STT."""

    name: ClassVar[EventName] = EventName.SPEECH_DETECTED
    text: str = ""
    is_final: bool = True
    wake: bool = False  # True se a frase continha a wake word "Jarvis"


@dataclass(frozen=True, slots=True)
class AudioCaptured(Event):
    """Trecho de áudio do sistema (loopback) transcrito."""

    name: ClassVar[EventName] = EventName.AUDIO_CAPTURED
    text: str = ""
    source: str = "loopback"


@dataclass(frozen=True, slots=True)
class ScreenChanged(Event):
    """A tela (ou uma região) mudou o suficiente para reprocessar."""

    name: ClassVar[EventName] = EventName.SCREEN_CHANGED
    region: str = "full"
    diff_ratio: float = 0.0


@dataclass(frozen=True, slots=True)
class OCRFinished(Event):
    """Texto extraído da tela pelo OCR."""

    name: ClassVar[EventName] = EventName.OCR_FINISHED
    text: str = ""
    region: str = "full"
    engine: str = ""


@dataclass(frozen=True, slots=True)
class VisionUpdated(Event):
    """Compreensão semântica da tela (OCR + visão LLM, quando ativa)."""

    name: ClassVar[EventName] = EventName.VISION_UPDATED
    summary: str = ""
    text: str = ""


@dataclass(frozen=True, slots=True)
class JarvisSpeaking(Event):
    """O Jarvis começou/terminou de falar (para silenciar o mic e evitar eco)."""

    name: ClassVar[EventName] = EventName.JARVIS_SPEAKING
    text: str = ""
    speaking: bool = True


@dataclass(frozen=True, slots=True)
class MicStateChanged(Event):
    """Transição de estado do microfone/wake-word.

    state: "idle" (aguardando wake word), "wake_triggered" (wake word detectada,
    aguardando comando), "command_listening" (capturando o comando do usuário).
    """

    name: ClassVar[EventName] = EventName.MIC_STATE
    state: str = "idle"


@dataclass(frozen=True, slots=True)
class BrainThinking(Event):
    """O cérebro começou/terminou de consultar o LLM.

    Usado para pausar o OCR/visão enquanto a LLM local (Ollama) roda — em CPUs
    fracas, os dois competindo por núcleo pode desacelerar (ou travar) a
    resposta do LLM.
    """

    name: ClassVar[EventName] = EventName.BRAIN_THINKING
    thinking: bool = True


@dataclass(frozen=True, slots=True)
class ControlCommand(Event):
    """Comando de controle enviado pelo cliente WS para ligar/desligar módulos.

    action: "enable" | "disable" | "toggle"
    module: "mic" | "loopback" | "vision" | "loopback_react" | "vision_react"
    """

    name: ClassVar[EventName] = EventName.CONTROL_CMD
    action: str = "toggle"
    module: str = ""
