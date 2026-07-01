"""Provedor de LLM local: **Ollama** (offline, gratuito, roda na própria
máquina). Usa a API REST nativa do Ollama (`/api/chat`) via `httpx`, já
dependência do projeto — sem precisar de chave de API."""

from __future__ import annotations

import asyncio
import time

import httpx

from ...core.config import Settings
from ...core.errors import EngineUnavailableError
from ...core.logging import get_logger
from ..models import ChatMessage

logger = get_logger("Brain")

# Prazo total (segundos) — independente do timeout interno do httpx, que em
# alguns ambientes (observado no Windows) pode não disparar de forma
# confiável para uma chamada que trava sem erro nem resposta.
HARD_TIMEOUT_S = 45.0


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{self._settings.ollama_base_url}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def complete(self, messages: list[ChatMessage]) -> str:
        started = time.monotonic()
        try:
            data = await asyncio.wait_for(self._post(messages), timeout=HARD_TIMEOUT_S)
        except TimeoutError as exc:
            raise EngineUnavailableError(
                f"Ollama não respondeu em {HARD_TIMEOUT_S:.0f}s (travado)."
            ) from exc
        except httpx.HTTPError as exc:
            raise EngineUnavailableError(f"Ollama indisponível: {exc}") from exc
        logger.debug("Ollama respondeu em %.1fs.", time.monotonic() - started)
        return (data.get("message", {}).get("content") or "").strip()

    async def _post(self, messages: list[ChatMessage]) -> dict:
        async with httpx.AsyncClient(timeout=HARD_TIMEOUT_S) as client:
            resp = await client.post(
                f"{self._settings.ollama_base_url}/api/chat",
                json={
                    "model": self._settings.ollama_model,
                    "messages": [m.as_dict() for m in messages],
                    "stream": False,
                    "options": {"temperature": 0.6},
                },
            )
            resp.raise_for_status()
            return resp.json()
