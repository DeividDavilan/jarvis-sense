"""Serviço de TTS — a "boca" do Jarvis.

`TTSService` é a fachada que o resto do sistema usa para falar. Ela:
- escolhe o motor (`ITTS`) conforme a configuração, com fallback automático
  para o motor offline (SAPI) quando o preferido não está disponível;
- publica `OnJarvisSpeaking(speaking=True/False)` ao redor de cada fala, para que
  o microfone possa se silenciar e evitar eco (requisito do prompt: voz única);
- nunca deixa um erro de TTS derrubar o sistema (`@safe_async`).

`create_tts()` é a fábrica (composition) — adicionar um motor novo (ElevenLabs,
OpenAI, Piper) é registrá-lo aqui, sem mudar quem chama `TTSService.speak`.
"""

from __future__ import annotations

from ..core.config import Settings, get_settings
from ..core.errors import safe_async
from ..core.event_types import JarvisSpeaking
from ..core.events import EventBus, get_event_bus
from ..core.logging import get_logger
from .adapters.edge_tts import EdgeTTS
from .adapters.sapi import SapiTTS
from .config import voice_config_from_settings
from .interfaces import ITTS

logger = get_logger("TTS")


def create_tts(settings: Settings, *, engine: str | None = None) -> ITTS:
    """Fábrica de motores TTS. `engine` força um motor; senão usa o da config."""
    voice = voice_config_from_settings(settings)
    choice = (engine or settings.tts_engine).lower()
    registry = {
        "edge": lambda: EdgeTTS(voice),
        "sapi": lambda: SapiTTS(voice),
    }
    factory = registry.get(choice)
    if factory is None:
        logger.warning("Motor TTS '%s' desconhecido; usando 'edge'.", choice)
        factory = registry["edge"]
    return factory()


class TTSService:
    """Fachada de fala com fallback automático e eventos de 'falando'."""

    def __init__(
        self,
        settings: Settings | None = None,
        bus: EventBus | None = None,
        primary: ITTS | None = None,
        fallback: ITTS | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._bus = bus or get_event_bus()
        self._primary = primary or create_tts(self._settings)
        # Fallback offline garantido no Windows: SAPI (nativo).
        self._fallback = fallback or SapiTTS(voice_config_from_settings(self._settings))
        self._active: ITTS | None = None

    async def _resolve(self) -> ITTS:
        """Escolhe (uma vez) o motor disponível: primário → fallback."""
        if self._active is not None:
            return self._active
        if await self._primary.is_available():
            self._active = self._primary
        else:
            logger.warning(
                "Motor TTS '%s' indisponível; caindo para '%s'.",
                self._primary.name,
                self._fallback.name,
            )
            self._active = self._fallback
        logger.info("Voz do Jarvis ativa: %s", self._active.name)
        return self._active

    @safe_async(module="TTS")
    async def speak(self, text: str) -> None:
        """Fala `text`. Emite OnJarvisSpeaking antes/depois."""
        if not text or not text.strip():
            return
        engine = await self._resolve()
        await self._bus.publish(JarvisSpeaking(text=text, speaking=True))
        try:
            await engine.speak(text)
        finally:
            await self._bus.publish(JarvisSpeaking(text=text, speaking=False))
