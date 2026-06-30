"""Interface de provedor de LLM — `ILLMProvider`.

Contrato desacoplado para qualquer modelo de linguagem (Groq/Llama, Anthropic/
Claude, OpenAI, modelos locais...). Recebe uma lista de mensagens no formato
de chat e devolve a resposta em texto.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import ChatMessage


@runtime_checkable
class ILLMProvider(Protocol):
    """Provedor de completude de chat."""

    name: str

    async def complete(self, messages: list[ChatMessage]) -> str:
        """Gera a resposta do assistente para a conversa `messages`."""
        ...

    async def is_available(self) -> bool:
        """True se o provedor e suas credenciais estão prontos."""
        ...
