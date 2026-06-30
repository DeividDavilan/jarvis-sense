"""Seleção de provedor de LLM. Espelha `src/server/orchestrator/provider.ts` do
Jarvis web: prefere o Groq (gratuito); cai para Anthropic. `JARVIS_LLM_PROVIDER`
força a escolha."""

from __future__ import annotations

from ..core.config import Settings
from .providers.anthropic import AnthropicProvider
from .providers.groq import GroqProvider


def build_providers(settings: Settings) -> tuple:
    """Retorna (primário, fallback) conforme a preferência e as chaves presentes.

    Ordem padrão: Groq primeiro (grátis), Anthropic como fallback. Se
    `JARVIS_LLM_PROVIDER=anthropic`, inverte.
    """
    groq = GroqProvider(settings)
    anthropic = AnthropicProvider(settings)
    if (settings.llm_provider or "").lower() == "anthropic":
        return anthropic, groq
    return groq, anthropic
