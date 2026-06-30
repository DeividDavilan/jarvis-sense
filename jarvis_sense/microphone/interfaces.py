"""Interface de fonte de áudio — `IAudioSource`.

Abstrai *de onde* vem a fala: microfone real (sounddevice), arquivo (testes) ou,
no futuro, qualquer outra fonte. Quem consome (o STT) só vê um fluxo assíncrono
de `Utterance`, nunca o dispositivo concreto.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from .models import Utterance


@runtime_checkable
class IAudioSource(Protocol):
    """Fonte que produz falas segmentadas por VAD/silêncio."""

    name: str

    def frames(self) -> AsyncIterator[bytes]:
        """Fluxo primitivo de quadros PCM crus de 30 ms (para wake word acústica)."""
        ...

    def utterances(self) -> AsyncIterator[Utterance]:
        """Itera (infinitamente, até cancelamento) sobre as falas detectadas."""
        ...

    async def is_available(self) -> bool:
        """True se o dispositivo/dependências estão prontos."""
        ...
