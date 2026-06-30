"""Ciclo de vida dos serviços.

Define o protocolo `Service` (start/stop assíncronos) e um `ServiceManager` que
sobe todos os serviços sob supervisão (`supervise` → reinício automático) e os
encerra de forma limpa. Cada capacidade (mic, tela, loopback, ponte...) é um
`Service`; o composition root (`services/app.py`) registra todos aqui.
"""

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

from .errors import supervise
from .logging import get_logger

logger = get_logger("Lifecycle")


@runtime_checkable
class Service(Protocol):
    """Contrato mínimo de um serviço de longa duração."""

    name: str

    async def run(self) -> None:
        """Laço principal do serviço. Deve respeitar cancelamento."""
        ...


class ServiceManager:
    """Sobe e derruba serviços. Cada serviço roda supervisionado (auto-restart)."""

    def __init__(self) -> None:
        self._services: list[Service] = []
        self._tasks: list[asyncio.Task[None]] = []

    def register(self, service: Service) -> None:
        self._services.append(service)
        logger.info("Serviço registrado: %s", service.name)

    async def start(self) -> None:
        """Inicia todos os serviços registrados sob supervisão."""
        for service in self._services:
            task = asyncio.create_task(
                supervise(service.run, name=service.name, module="Lifecycle"),
                name=service.name,
            )
            self._tasks.append(task)
        logger.info("%d serviço(s) iniciado(s).", len(self._tasks))

    async def stop(self) -> None:
        """Cancela e aguarda todos os serviços encerrarem."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Todos os serviços foram encerrados.")

    async def run_forever(self) -> None:
        """Sobe tudo e bloqueia até Ctrl+C / cancelamento."""
        await self.start()
        try:
            await asyncio.Event().wait()  # dorme para sempre
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            await self.stop()
