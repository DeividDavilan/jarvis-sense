"""Interface de TTS — `ITTS`.

Contrato desacoplado para qualquer motor de voz (edge-tts, SAPI, ElevenLabs,
OpenAI, Piper...). Adicionar um motor novo = implementar esta interface e
registrá-lo na fábrica (`services.create_tts`), sem tocar no resto do sistema
(Princípio Aberto/Fechado).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ITTS(Protocol):
    """Motor de texto-para-fala."""

    name: str

    async def speak(self, text: str) -> None:
        """Sintetiza e reproduz `text` de forma síncrona (retorna ao terminar
        de falar). Deve ser seguro chamar com string vazia (no-op)."""
        ...

    async def is_available(self) -> bool:
        """True se o motor e suas dependências estão prontos para uso."""
        ...
