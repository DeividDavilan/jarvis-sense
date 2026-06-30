"""Visão semântica DESLIGADA (padrão). Não chama nenhum modelo: devolve "" e
deixa o pipeline operar só com OCR (gratuito). É o default seguro e sem custo."""

from __future__ import annotations


class NullVision:
    name = "off"

    async def is_available(self) -> bool:
        return True

    async def describe(self, png: bytes, ocr_text: str) -> str:  # noqa: ARG002
        return ""
