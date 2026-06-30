"""Interface de fonte de loopback — `ILoopbackSource`.

Mesma forma da `IAudioSource` do microfone (produz `Utterance`s), mas a origem é
o áudio que o computador reproduz. Manter a mesma forma permite reaproveitar o
STT sem mudanças.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from ..microphone.models import Utterance


@runtime_checkable
class ILoopbackSource(Protocol):
    name: str

    def utterances(self) -> AsyncIterator[Utterance]:
        """Itera sobre trechos de fala detectados no áudio do sistema."""
        ...

    async def is_available(self) -> bool:
        ...
