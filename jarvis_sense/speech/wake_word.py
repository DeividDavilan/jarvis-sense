"""Detecção da palavra de ativação ("Jarvis").

Estratégia padrão (gratuita e robusta): detecção **textual** sobre a transcrição
— mesma abordagem do Jarvis web (`src/lib/voice/intent.ts`). Normaliza acentos e
procura a wake word; devolve também o "resto" da frase (o comando dito logo após
"Jarvis ...").

Um detector **acústico** opcional (openWakeWord) pode ser plugado depois para
ativação antes mesmo do STT — fica como melhoria futura atrás da mesma ideia.
"""

from __future__ import annotations

import unicodedata


def _normalize(text: str) -> str:
    """Minúsculas + remoção de acentos, para casar 'Járvis'/'jarvis'."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


class WakeWordDetector:
    """Detector textual da wake word."""

    def __init__(self, wake_word: str = "jarvis") -> None:
        self._wake = _normalize(wake_word)

    def detect(self, transcript: str) -> tuple[bool, str]:
        """Retorna (achou, comando_após_wake).

        Se a wake word aparece, `comando_após_wake` é o texto que vem depois dela
        (pode ser vazio, quando o usuário só chama "Jarvis"). Se não aparece,
        retorna (False, "").
        """
        norm = _normalize(transcript)
        pos = norm.find(self._wake)
        if pos == -1:
            return False, ""
        remainder = transcript[pos + len(self._wake):]
        remainder = remainder.lstrip(" ,.!:;-").strip()
        return True, remainder
