"""Servidor WebSocket de eventos de percepção (aditivo).

`PerceptionWebSocketServer` é um `Service` que assina TODOS os eventos do
barramento e os transmite, em JSON, para qualquer cliente conectado em
`ws://<host>:<port>`. É o espelho do canal SSE do Jarvis web (`/api/stream`),
mas no sentido Python → consumidores (ex.: um futuro Electron/HUD nativo).

Cada frame é o `to_payload()` do evento: `{"type": "OnOCRFinished", ...}`.

Não altera o app web — é um canal novo e independente.
"""

from __future__ import annotations

import asyncio
import json

from ..core.config import Settings, get_settings
from ..core.event_types import ControlCommand, Event
from ..core.events import EventBus, get_event_bus
from ..core.logging import get_logger

logger = get_logger("Bridge")


class PerceptionWebSocketServer:
    name = "ws-bridge"

    def __init__(self, settings: Settings | None = None, bus: EventBus | None = None) -> None:
        self._settings = settings or get_settings()
        self._bus = bus or get_event_bus()
        self._clients: set = set()

    async def run(self) -> None:
        try:
            import websockets
        except ImportError:
            logger.error("Pacote 'websockets' ausente; ponte WS inativa.")
            return

        unsubscribe = self._bus.subscribe_all(self._on_event)
        host, port = self._settings.ws_host, self._settings.ws_port
        try:
            async with websockets.serve(self._handle_client, host, port):
                logger.info("Ponte WebSocket de percepção em ws://%s:%d", host, port)
                await asyncio.Event().wait()
        finally:
            unsubscribe()

    async def _handle_client(self, websocket) -> None:
        self._clients.add(websocket)
        logger.info("Cliente WS conectado (%d total).", len(self._clients))
        try:
            async for raw in websocket:
                await self._on_client_message(raw)
        except Exception:  # noqa: BLE001 — desconexão abrupta
            pass
        finally:
            self._clients.discard(websocket)
            logger.info("Cliente WS desconectado (%d total).", len(self._clients))

    async def _on_client_message(self, raw: str) -> None:
        """Processa comandos enviados pelo cliente (painel clicável)."""
        try:
            msg = json.loads(raw)
        except Exception:  # noqa: BLE001
            return
        msg_type = msg.get("type", "")

        if msg_type == "control":
            action = str(msg.get("action", "toggle"))
            module = str(msg.get("module", ""))
            if module:
                await self._bus.publish(ControlCommand(action=action, module=module))
                logger.info("Comando de controle recebido: %s %s", action, module)
        else:
            logger.debug("Mensagem WS desconhecida ignorada: %s", msg_type)

    async def _on_event(self, event: Event) -> None:
        if not self._clients:
            return
        message = json.dumps(event.to_payload(), default=str, ensure_ascii=False)
        # Envia em paralelo; clientes que falharem são descartados silenciosamente.
        await asyncio.gather(
            *(self._safe_send(ws, message) for ws in list(self._clients)),
            return_exceptions=True,
        )

    async def _safe_send(self, ws, message: str) -> None:
        try:
            await ws.send(message)
        except Exception:  # noqa: BLE001
            self._clients.discard(ws)
