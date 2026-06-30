"""Interface de STT — `ISTT`.

Contrato desacoplado para qualquer motor de reconhecimento de fala (Groq Whisper,
faster-whisper local, Whisper.cpp, etc.). Recebe uma `Utterance` (PCM) e devolve
o texto transcrito.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..microphone.models import Utterance


@runtime_checkable
class ISTT(Protocol):
    """Motor de fala-para-texto."""

    name: str

    async def transcribe(self, utterance: Utterance) -> str:
        """Transcreve a fala. Retorna texto (possivelmente vazio)."""
        ...

    async def is_available(self) -> bool:
        """True se o motor e suas dependências/credenciais estão prontos."""
        ...
