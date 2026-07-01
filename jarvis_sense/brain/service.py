"""Serviço cérebro — a fatia vertical que conecta tudo.

`BrainService` assina `OnSpeechDetected` no barramento e, quando o usuário fala
após a wake word, monta a conversa, consulta o LLM (Groq → Anthropic) e responde
pela voz do Jarvis (`TTSService`). Mantém um histórico curto para dar contexto.

Modo de conversa: ao ouvir só "Jarvis" (sem comando), responde "Sim, senhor?" e
fica "acordado" por um curto período, aceitando a próxima fala como comando sem
exigir a wake word de novo — espelhando o comportamento do `VoiceConsole.tsx` do
Jarvis web.

Não conhece microfone nem STT: só reage a eventos e fala. Isso o mantém
desacoplado e testável sem áudio real.
"""

from __future__ import annotations

import time
from collections import deque

from ..core.config import Settings, get_settings
from ..core.errors import safe_async
from ..core.event_types import BrainThinking, ControlCommand, EventName
from ..core.events import EventBus, get_event_bus
from ..core.logging import get_logger
from ..tts.services import TTSService
from .config import build_providers
from .interfaces import ILLMProvider
from .models import JARVIS_SYSTEM_PROMPT, ChatMessage

logger = get_logger("Brain")

AWAKE_WINDOW_S = 60.0  # tempo que o Jarvis fica aguardando comando sem wake word
# 60s porque a janela começa a contar no instante do wake, mas o comando só
# chega aqui depois do "Sim, senhor?" falado + VAD + STT — e o faster-whisper
# local pode levar 30-40s pra carregar o modelo + transcrever na primeira vez
# de um processo novo (observado ao vivo). Um valor curto descartava o
# primeiro comando em silêncio (sem log nem resposta) com o STT "frio".
HISTORY_TURNS = 6      # pares usuário/assistente mantidos como contexto


class BrainService:
    name = "brain"

    def __init__(
        self,
        settings: Settings | None = None,
        bus: EventBus | None = None,
        tts: TTSService | None = None,
        primary: ILLMProvider | None = None,
        fallback: ILLMProvider | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._bus = bus or get_event_bus()
        self._tts = tts or TTSService(self._settings, self._bus)

        built_primary, built_fallback = build_providers(self._settings)
        self._primary = primary or built_primary
        self._fallback = fallback or built_fallback
        self._active: ILLMProvider | None = None

        self._history: deque[ChatMessage] = deque(maxlen=HISTORY_TURNS * 2)
        self._awake_until = 0.0
        self._screen_context: str = ""
        self._loopback_react = self._settings.loopback_react
        self._vision_react = self._settings.vision_react

        self._bus.subscribe(EventName.SPEECH_DETECTED, self._on_speech)
        self._bus.subscribe(EventName.VISION_UPDATED, self._on_vision)
        self._bus.subscribe(EventName.AUDIO_CAPTURED, self._on_system_audio)
        self._bus.subscribe(EventName.CONTROL_CMD, self._on_control)

    @property
    def tts(self) -> TTSService:
        """Voz do Jarvis (reutilizável por outros serviços, ex.: despacho)."""
        return self._tts

    async def run(self) -> None:
        """O cérebro é reativo (assina eventos); o laço só mantém o serviço vivo."""
        import asyncio

        logger.info("Cérebro online (provedor preferido: %s).", self._primary.name)
        await asyncio.Event().wait()

    # --- controle de módulos ---------------------------------------------------
    def _on_control(self, event: ControlCommand) -> None:
        if event.module == "loopback_react":
            val = event.action != "disable" if event.action != "toggle" else not self._loopback_react
            self._loopback_react = val
            logger.info("Reação ao loopback %s.", "ativada" if val else "desativada")
        elif event.module == "vision_react":
            val = event.action != "disable" if event.action != "toggle" else not self._vision_react
            self._vision_react = val
            logger.info("Reação à visão %s.", "ativada" if val else "desativada")

    # --- visão semântica → contexto -------------------------------------------
    @safe_async(module="Brain")
    async def _on_vision(self, event) -> None:  # noqa: ANN001
        if not event.summary:
            return
        self._screen_context = event.summary
        logger.debug("Contexto de tela atualizado: %s", event.summary[:80])

        if self._vision_react:
            reply = await self._think(
                f"[Contexto: a tela mudou] {event.summary}",
                extra_system="Comente brevemente o que mudou na tela, em uma frase curta.",
            )
            if reply:
                await self._tts.speak(reply)

    # --- áudio do sistema → contexto ------------------------------------------
    @safe_async(module="Brain")
    async def _on_system_audio(self, event) -> None:  # noqa: ANN001
        if not event.text or not self._loopback_react:
            return
        logger.info("Áudio do sistema recebido pelo cérebro: %r", event.text[:80])
        reply = await self._think(
            f"[Áudio do sistema] {event.text}",
            extra_system=(
                "O áudio a seguir foi capturado do sistema (loopback), não é um comando "
                "direto do senhor. Reaja de forma breve e relevante, apenas se fizer sentido."
            ),
        )
        if reply:
            await self._tts.speak(reply)

    # --- manipulação de fala ---------------------------------------------------
    @safe_async(module="Brain")
    async def _on_speech(self, event) -> None:  # noqa: ANN001
        now = time.time()
        awake = now < self._awake_until

        if not event.wake and not awake:
            logger.warning(
                "Comando ignorado (%r): fora da janela de conversa (%.1fs após o wake).",
                event.text, now - self._awake_until + AWAKE_WINDOW_S,
            )
            return  # ignora fala sem wake word fora da janela de conversa

        command = event.text.strip()

        # "Jarvis" sozinho → confirma e abre janela de conversa.
        if event.wake and not command:
            self._awake_until = now + AWAKE_WINDOW_S
            await self._tts.speak("Sim, senhor?")
            return

        if not command:
            return

        self._awake_until = now + AWAKE_WINDOW_S  # mantém a conversa aberta
        reply = await self._think(command)
        if reply:
            await self._tts.speak(reply)

    # --- raciocínio ------------------------------------------------------------
    async def _resolve_provider(self) -> ILLMProvider | None:
        if self._active is not None:
            return self._active
        if await self._primary.is_available():
            self._active = self._primary
        elif await self._fallback.is_available():
            logger.warning(
                "Provedor '%s' indisponível; usando '%s'.",
                self._primary.name,
                self._fallback.name,
            )
            self._active = self._fallback
        else:
            return None
        logger.info("Provedor de IA ativo: %s", self._active.name)
        return self._active

    async def _think(self, command: str, extra_system: str = "") -> str:
        provider = await self._resolve_provider()
        if provider is None:
            return "Nenhum provedor de inteligência está configurado, senhor."

        self._history.append(ChatMessage(role="user", content=command))

        system = JARVIS_SYSTEM_PROMPT
        if self._screen_context:
            system += f"\n\nContexto atual da tela: {self._screen_context}"
        if extra_system:
            system += f"\n\n{extra_system}"

        messages = [
            ChatMessage(role="system", content=system),
            *self._history,
        ]
        await self._bus.publish(BrainThinking(thinking=True))
        try:
            reply = await self._complete_with_fallback(provider, messages)
        finally:
            await self._bus.publish(BrainThinking(thinking=False))
        if reply:
            self._history.append(ChatMessage(role="assistant", content=reply))
        logger.info("Resposta: %r", reply)
        return reply

    async def _complete_with_fallback(self, provider: ILLMProvider, messages: list[ChatMessage]) -> str:
        """Nunca deixa o Jarvis "mudo": se o provedor ativo falhar (travar,
        cair), tenta uma vez o outro provedor configurado antes de desistir
        com uma resposta falada de erro (em vez de nenhuma resposta)."""
        try:
            return await provider.complete(messages)
        except Exception as exc:  # noqa: BLE001 — qualquer falha de provedor
            other = self._fallback if provider is self._primary else self._primary
            logger.warning("Provedor '%s' falhou (%s); tentando '%s'.", provider.name, exc, other.name)
            try:
                reply = await other.complete(messages)
                self._active = other  # a falha indica que o outro é mais confiável agora
                return reply
            except Exception as exc2:  # noqa: BLE001
                logger.error("Provedor de fallback '%s' também falhou: %s", other.name, exc2)
                return "Desculpe, senhor, os provedores de IA estão indisponíveis no momento."
