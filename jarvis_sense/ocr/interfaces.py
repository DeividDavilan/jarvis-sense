"""Interface de OCR — `IOCR`.

Contrato desacoplado para qualquer motor de OCR (RapidOCR, Tesseract, PaddleOCR,
ou no futuro uma API de visão). Recebe os bytes de uma imagem PNG e devolve o
texto extraído.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IOCR(Protocol):
    name: str

    async def extract(self, png: bytes) -> str:
        """Extrai e devolve o texto contido na imagem PNG."""
        ...

    async def is_available(self) -> bool:
        ...
