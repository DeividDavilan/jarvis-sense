"""Provedor de LLM padrão: **Groq** (gratuito, Llama 3.3). Espelha o provider
`groq` do Jarvis web (`src/server/orchestrator/groq.ts`), reaproveitando a mesma
chave e modelo."""

from __future__ import annotations

import asyncio

from ...core.config import Settings
from ...core.errors import EngineUnavailableError
from ...core.logging import get_logger
from ..models import ChatMessage

logger = get_logger("Brain")


class GroqProvider:
    name = "groq"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    async def is_available(self) -> bool:
        if not self._settings.has_groq:
            return False
        try:
            import groq  # noqa: F401
        except ImportError:
            return False
        return True

    def _ensure_client(self):
        if self._client is None:
            try:
                from groq import Groq
            except ImportError as exc:
                raise EngineUnavailableError("Pacote 'groq' não instalado.") from exc
            self._client = Groq(api_key=self._settings.groq_api_key)
        return self._client

    async def complete(self, messages: list[ChatMessage]) -> str:
        if not self._settings.has_groq:
            raise EngineUnavailableError("GROQ_API_KEY ausente.")
        return await asyncio.to_thread(self._complete_blocking, messages)

    def _complete_blocking(self, messages: list[ChatMessage]) -> str:
        client = self._ensure_client()
        resp = client.chat.completions.create(
            model=self._settings.groq_model,
            messages=[m.as_dict() for m in messages],
            temperature=0.6,
            max_tokens=400,
        )
        return (resp.choices[0].message.content or "").strip()
