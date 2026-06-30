"""Interface de captura de tela — `IScreenCapture`.

Abstrai *como* a tela é capturada (mss real, imagem fixa em testes). Produz um
`Frame` com PNG comprimido + assinatura perceptual.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import Frame, Region


@runtime_checkable
class IScreenCapture(Protocol):
    name: str

    async def grab(self, region: Region) -> Frame:
        """Captura `region` e devolve um `Frame` (PNG + assinatura)."""
        ...

    async def is_available(self) -> bool:
        ...
