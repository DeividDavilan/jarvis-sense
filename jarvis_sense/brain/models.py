"""Modelos de dados do cérebro: mensagens de chat e o prompt-base do Jarvis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


# Persona do Jarvis. Respostas faladas → curtas, naturais, em pt-BR. Trata o
# usuário por "senhor" (estilo Jarvis/Homem de Ferro), conforme o projeto.
JARVIS_SYSTEM_PROMPT = (
    "Você é o J.A.R.V.I.S., o assistente de IA pessoal do Deivid. "
    "Fale sempre em português do Brasil, de forma natural, educada e concisa — "
    "suas respostas serão FALADAS em voz alta, então evite listas longas, código "
    "ou formatação; prefira uma ou duas frases diretas. Trate o usuário por "
    "'senhor' com elegância discreta. Se não souber algo, diga com honestidade."
)
