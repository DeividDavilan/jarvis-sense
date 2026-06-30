"""Serviço de despacho: comando de voz → tarefa no Jarvis web.

`TaskDispatchService` assina `OnSpeechDetected` e, quando o comando começa com um
gatilho de tarefa ("criar tarefa…", "nova tarefa…", "anota uma tarefa…"),
extrai o título e despacha ao Jarvis pelo `JarvisClient` (APIs existentes).
Opcionalmente confirma por voz (TTS), se um for injetado.

Regra simples e extensível — outros gatilhos/intenções entram aqui sem tocar no
cérebro nem no app web. É o que cumpre o critério da fase: "um comando de voz
cria uma tarefa no Jarvis sem alterar o sistema web".
"""

from __future__ import annotations

import re

from ..core.config import Settings, get_settings
from ..core.errors import safe_async
from ..core.event_types import EventName
from ..core.events import EventBus, get_event_bus
from ..core.logging import get_logger
from .jarvis_client import JarvisClient

logger = get_logger("Bridge")

# Gatilhos de criação de tarefa (com/sem acento). Captura o título depois deles.
# O separador após o substantivo é flexível: espaço, ":", ",", "-" (ou combinação),
# seguido de uma preposição opcional ("de"/"para"/"pra").
_TRIGGER = re.compile(
    r"^\s*(?:criar?|cria|nova|novo|anota[r]?|adiciona[r]?)\s+(?:uma?\s+)?"
    r"(?:tarefa|task|atividade)\b[\s:,\-]*"
    r"(?:de\s+|para\s+|pra\s+)?(?P<title>.+)$",
    re.IGNORECASE,
)


class TaskDispatchService:
    name = "task-dispatch"

    def __init__(
        self,
        settings: Settings | None = None,
        bus: EventBus | None = None,
        client: JarvisClient | None = None,
        tts=None,
    ) -> None:
        self._settings = settings or get_settings()
        self._bus = bus or get_event_bus()
        self._client = client or JarvisClient(self._settings)
        self._tts = tts
        self._bus.subscribe(EventName.SPEECH_DETECTED, self._on_speech)

    async def run(self) -> None:
        import asyncio

        logger.info("Despacho de tarefas por voz ativo (alvo: %s).", self._settings.web_url)
        await asyncio.Event().wait()

    @staticmethod
    def parse_title(command: str) -> str | None:
        """Extrai o título da tarefa de um comando, ou None se não for tarefa."""
        match = _TRIGGER.match(command or "")
        if not match:
            return None
        return match.group("title").strip().rstrip(".").strip() or None

    @safe_async(module="Bridge")
    async def _on_speech(self, event) -> None:  # noqa: ANN001
        title = self.parse_title(event.text)
        if not title:
            return
        logger.info("Comando de tarefa reconhecido: %r", title)
        task = await self._client.dispatch(title)
        if self._tts is not None:
            if task:
                await self._tts.speak(f"Tarefa criada, senhor: {title}.")
            else:
                await self._tts.speak("Não consegui falar com o Jarvis, senhor.")
