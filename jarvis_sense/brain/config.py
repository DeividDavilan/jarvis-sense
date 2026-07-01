"""Seleção de provedor de LLM. Espelha `src/server/orchestrator/provider.ts` do
Jarvis web: prefere o Groq (gratuito); cai para Anthropic. `JARVIS_LLM_PROVIDER`
força a escolha (inclui "ollama", 100% local/offline)."""

from __future__ import annotations

from ..core.config import Settings
from .providers.anthropic import AnthropicProvider
from .providers.groq import GroqProvider
from .providers.ollama import OllamaProvider


def build_providers(settings: Settings) -> tuple:
    """Retorna (primário, fallback) conforme a preferência e as chaves presentes.

    Ordem padrão: Groq primeiro (grátis), Anthropic como fallback.
    `JARVIS_LLM_PROVIDER=anthropic` ou `=ollama` força o respectivo provedor
    como primário, com Groq como fallback em nuvem se o local cair.
    """
    groq = GroqProvider(settings)
    anthropic = AnthropicProvider(settings)
    ollama = OllamaProvider(settings)
    choice = (settings.llm_provider or "").lower()
    if choice == "anthropic":
        return anthropic, groq
    if choice == "ollama":
        return ollama, groq
    return groq, anthropic
