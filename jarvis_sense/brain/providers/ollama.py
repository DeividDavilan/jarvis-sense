"""Provedor de LLM local: **Ollama** (offline, gratuito, roda na própria
máquina). Usa a API REST nativa do Ollama (`/api/chat`) via `httpx`, já
dependência do projeto — sem precisar de chave de API."""

from __future__ import annotations

import httpx

from ...core.config import Settings
from ...core.errors import EngineUnavailableError
from ...core.logging import get_logger
from ..models import ChatMessage

logger = get_logger("Brain")


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
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
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
                data = resp.json()
        except httpx.HTTPError as exc:
            raise EngineUnavailableError(f"Ollama indisponível: {exc}") from exc
        return (data.get("message", {}).get("content") or "").strip()
