"""Provedor de LLM fallback: **Anthropic / Claude**. Espelha o provider
`anthropic` do Jarvis web. A mensagem `system` vai no parâmetro próprio da API
de Mensagens (não na lista de mensagens)."""

from __future__ import annotations

import asyncio

from ...core.config import Settings
from ...core.errors import EngineUnavailableError
from ...core.logging import get_logger
from ..models import ChatMessage

logger = get_logger("Brain")

MODEL = "claude-opus-4-8"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    async def is_available(self) -> bool:
        if not self._settings.has_anthropic:
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def _ensure_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise EngineUnavailableError("Pacote 'anthropic' não instalado.") from exc
            self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        return self._client

    async def complete(self, messages: list[ChatMessage]) -> str:
        if not self._settings.has_anthropic:
            raise EngineUnavailableError("ANTHROPIC_API_KEY ausente.")
        return await asyncio.to_thread(self._complete_blocking, messages)

    def _complete_blocking(self, messages: list[ChatMessage]) -> str:
        client = self._ensure_client()
        system = " ".join(m.content for m in messages if m.role == "system")
        convo = [m.as_dict() for m in messages if m.role != "system"]
        resp = client.messages.create(
            model=MODEL,
            system=system or None,
            messages=convo,
            max_tokens=400,
            temperature=0.6,
        )
        parts = [block.text for block in resp.content if getattr(block, "type", "") == "text"]
        return "".join(parts).strip()
