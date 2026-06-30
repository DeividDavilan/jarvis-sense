"""Modelos do módulo de tela."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Region:
    """Região retangular de captura. `None` em tudo = tela inteira primária."""

    left: int = 0
    top: int = 0
    width: int = 0   # 0 = automático (tela toda)
    height: int = 0
    label: str = "full"

    @property
    def is_full(self) -> bool:
        return self.width == 0 and self.height == 0


@dataclass(frozen=True, slots=True)
class Frame:
    """Um quadro capturado.

    `png` é a imagem comprimida (bytes PNG) — pronta para OCR ou para enviar a
    um modelo de visão. `signature` é uma assinatura perceptual pequena (bytes
    de uma miniatura em tons de cinza) usada para detectar mudança e cachear OCR.
    """

    png: bytes
    width: int
    height: int
    signature: bytes
    region: Region
