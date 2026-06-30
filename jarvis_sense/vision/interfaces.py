"""Interface de visão semântica — `IVision`.

Camada acima do OCR: dado um quadro (PNG) e o texto já extraído, devolve uma
*compreensão* da tela (o que é, o que está acontecendo). Implementações futuras:
Claude Vision, GPT-4o Vision, Gemini Vision, YOLO/OpenCV. Por padrão fica
desligada (`NullVision`), mantendo tudo gratuito até você ativar.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IVision(Protocol):
    name: str

    async def describe(self, png: bytes, ocr_text: str) -> str:
        """Devolve um resumo do que a tela mostra. Pode usar `ocr_text` como
        apoio. Retorna "" quando não há compreensão semântica (só OCR)."""
        ...

    async def is_available(self) -> bool:
        ...
