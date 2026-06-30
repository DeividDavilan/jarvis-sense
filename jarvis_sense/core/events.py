"""Barramento de eventos assíncrono (pub/sub).

Espelho conceitual do `src/server/events.ts` do Jarvis web (lá um `EventEmitter`
faz fan-out para os clientes SSE). Aqui, um `EventBus` async distribui cada
`Event` para todos os assinantes do tópico correspondente — e para os
assinantes "globais" (que recebem tudo, usados pela ponte WebSocket e pelos
logs).

Princípios:
- Desacoplamento total: módulos publicam/assinam eventos, nunca se chamam.
- Robustez: a exceção de um assinante NUNCA derruba o publish nem afeta os
  outros assinantes (cada callback roda isolado).
- Assíncrono: assinantes podem ser corrotinas (`async def`) ou funções comuns.
"""

from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Union

from .event_types import Event, EventName
from .logging import get_logger

logger = get_logger("Events")

# Um handler pode ser síncrono ou assíncrono.
Handler = Callable[[Event], Union[None, Awaitable[None]]]

_GLOBAL = "*"


class EventBus:
    """Pub/sub assíncrono em processo. Crie um por aplicação (singleton via
    `get_event_bus()`)."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)

    # --- assinatura ------------------------------------------------------------
    def subscribe(self, name: EventName | str, handler: Handler) -> Callable[[], None]:
        """Assina um tópico específico. Retorna uma função para desinscrever."""
        topic = name.value if isinstance(name, EventName) else name
        self._subs[topic].append(handler)
        return lambda: self._unsub(topic, handler)

    def subscribe_all(self, handler: Handler) -> Callable[[], None]:
        """Assina TODOS os eventos (ex.: ponte WebSocket, telemetria)."""
        return self.subscribe(_GLOBAL, handler)

    def _unsub(self, topic: str, handler: Handler) -> None:
        try:
            self._subs[topic].remove(handler)
        except ValueError:
            pass

    # --- publicação ------------------------------------------------------------
    async def publish(self, event: Event) -> None:
        """Entrega `event` a todos os assinantes do seu tópico e aos globais.

        Cada handler é executado de forma isolada: erros são registrados, nunca
        propagados.
        """
        handlers = [*self._subs.get(event.name.value, ()), *self._subs.get(_GLOBAL, ())]
        for handler in handlers:
            await self._dispatch(handler, event)

    async def _dispatch(self, handler: Handler, event: Event) -> None:
        try:
            result = handler(event)
            if inspect.isawaitable(result):
                await result
        except Exception:  # noqa: BLE001 — isolamento intencional
            logger.exception("Handler de evento falhou para %s", event.name.value)


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Retorna o barramento único da aplicação."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_event_bus() -> None:
    """Reseta o barramento (uso em testes)."""
    global _bus
    _bus = None


# Conveniência para callers síncronos que estão fora de um loop async.
def publish_soon(event: Event) -> None:
    """Agenda o publish no loop em execução, se houver; caso contrário ignora.

    Útil para callbacks de bibliotecas de áudio que rodam em threads próprias.
    """
    bus = get_event_bus()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("publish_soon sem loop ativo; evento %s descartado", event.name.value)
        return
    loop.call_soon_threadsafe(lambda: asyncio.ensure_future(bus.publish(event)))
