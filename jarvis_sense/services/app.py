"""Composition root da aplicação Jarvis Sense.

Aqui as implementações concretas são instanciadas e ligadas ao barramento de
eventos e ao `ServiceManager`. Cada fase do projeto "pluga" seus serviços neste
arquivo — sem que um módulo precise conhecer o outro.

Estado atual (Fase 0): a fundação sobe vazia e fica viva. À medida que as fases
avançam, os blocos comentados abaixo são ativados. Manter este arquivo como o
ponto único de montagem é o que permite crescer sem reescrever a arquitetura.
"""

from __future__ import annotations

from ..core.config import Settings, get_settings
from ..core.events import EventBus, get_event_bus
from ..core.lifecycle import ServiceManager
from ..core.logging import get_logger

logger = get_logger("App")


class JarvisSenseApp:
    """Orquestra a montagem e o ciclo de vida de todo o subsistema."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.bus: EventBus = get_event_bus()
        self.manager = ServiceManager()

    def assemble(self) -> "JarvisSenseApp":
        """Instancia e registra os serviços ativos. Idempotente."""
        logger.info("Montando Jarvis Sense (perfil: %s)…", self._profile())

        # Telemetria: loga todos os eventos que passam pelo barramento.
        self.bus.subscribe_all(self._log_event)

        # --- Fase 3 — Cérebro (reativo: pensa e fala) — ATIVO ------------------
        from ..brain.service import BrainService

        brain = BrainService(self.settings, self.bus)
        self.manager.register(brain)

        # --- Fase 6 — Ponte: servidor WS de percepção + despacho de tarefas ----
        from ..bridge.dispatch import TaskDispatchService
        from ..bridge.ws_server import PerceptionWebSocketServer

        self.manager.register(PerceptionWebSocketServer(self.settings, self.bus))
        # Reutiliza a voz do cérebro para confirmar a criação de tarefas.
        self.manager.register(TaskDispatchService(self.settings, self.bus, tts=brain.tts))

        # --- Fase 2 — Voz do usuário (mic + STT) — ATIVO ----------------------
        # Degrada com elegância: se as libs de áudio/microfone não estiverem
        # instaladas, o serviço apenas loga e fica inativo (não derruba nada).
        from ..speech.services import VoiceInputService

        self.manager.register(VoiceInputService(self.settings, self.bus))

        # --- Fase 6 — Ponte WebSocket (eventos de percepção) -------------------
        # from ..bridge.ws_server import PerceptionWebSocketServer
        # self.manager.register(PerceptionWebSocketServer(self.bus, self.settings))

        # --- Fase 4 — Tela + OCR + visão — ATIVO ------------------------------
        # Degrada com elegância: sem mss/Pillow/OCR, apenas loga e fica inativo.
        from ..vision.services import VisionService

        self.manager.register(VisionService(self.settings, self.bus))

        # --- Fase 5 — Áudio do sistema (loopback) — ATIVO ---------------------
        # Degrada com elegância: sem PyAudioWPatch, apenas loga e fica inativo.
        from ..audio.services import LoopbackService

        self.manager.register(LoopbackService(self.settings, self.bus))

        return self

    async def run(self) -> None:
        """Sobe tudo e bloqueia até Ctrl+C."""
        self.assemble()
        logger.info("Jarvis Sense online. Pressione Ctrl+C para encerrar.")
        await self.manager.run_forever()

    # --- internos --------------------------------------------------------------
    def _log_event(self, event) -> None:  # noqa: ANN001 — Event do core
        logger.debug("evento %s", event.name.value)

    def _profile(self) -> str:
        parts = []
        if (self.settings.llm_provider or "").lower() == "ollama":
            parts.append("ollama")
        if self.settings.has_groq:
            parts.append("groq")
        if self.settings.has_anthropic:
            parts.append("anthropic")
        return "+".join(parts) or "sem-LLM"
