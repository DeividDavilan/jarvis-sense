"""Visão semântica via **Claude Vision** (opcional, gera custo de API).

Ativada com `JARVIS_VISION_ENGINE=anthropic` + `ANTHROPIC_API_KEY`. Envia o PNG
da tela ao Claude e pede um resumo curto em pt-BR do que está sendo exibido. É o
exemplo de como plugar um modelo de visão sem mudar o resto — qualquer outro
(GPT-4o, Gemini) entra do mesmo jeito, implementando `IVision`.
"""

from __future__ import annotations

import asyncio
import base64

from ...core.config import Settings
from ...core.errors import EngineUnavailableError
from ...core.logging import get_logger

logger = get_logger("Vision")

MODEL = "claude-opus-4-8"
PROMPT = (
    "Descreva em uma ou duas frases, em português do Brasil, o que esta tela do "
    "computador está mostrando (aplicativo, conteúdo principal e o que o usuário "
    "parece estar fazendo). Seja direto."
)


class AnthropicVision:
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
                raise EngineUnavailableError("Pacote 'anthropic' ausente.") from exc
            self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        return self._client

    async def describe(self, png: bytes, ocr_text: str) -> str:  # noqa: ARG002
        if not self._settings.has_anthropic:
            return ""
        return await asyncio.to_thread(self._describe_blocking, png)

    def _describe_blocking(self, png: bytes) -> str:
        client = self._ensure_client()
        b64 = base64.standard_b64encode(png).decode("ascii")
        resp = client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": PROMPT},
                    ],
                }
            ],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts).strip()
