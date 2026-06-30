"""Fábrica da camada de visão semântica. Padrão = desligada (NullVision)."""

from __future__ import annotations

from ..core.config import Settings
from .adapters.null_vision import NullVision
from .interfaces import IVision


def create_vision(settings: Settings) -> IVision:
    """Cria a implementação de `IVision` conforme `JARVIS_VISION_ENGINE`."""
    choice = (settings.vision_engine or "off").lower()
    if choice == "anthropic":
        from .adapters.anthropic_vision import AnthropicVision

        return AnthropicVision(settings)
    return NullVision()
