"""Demo do cérebro por TEXTO (valida o LLM + a voz sem precisar de microfone).

    python -m jarvis_sense.brain.demo

Digite uma frase; o Jarvis pensa (Groq/Anthropic) e responde — falando em voz
alta, igual ao fluxo de voz, mas com a entrada vinda do teclado. Encerre com
'sair' ou Ctrl+C. Útil para conferir a fatia vertical antes de ligar o mic.
"""

from __future__ import annotations

import asyncio

from ..core.config import get_settings
from ..core.event_types import SpeechDetected
from ..core.events import get_event_bus
from .service import BrainService


async def _main() -> None:
    settings = get_settings()
    bus = get_event_bus()
    BrainService(settings, bus)  # assina o barramento
    print("Jarvis (cérebro) pronto. Digite e tecle Enter. 'sair' para encerrar.\n")

    while True:
        try:
            text = await asyncio.to_thread(input, "você> ")
        except (EOFError, KeyboardInterrupt):
            break
        if text.strip().lower() in {"sair", "exit", "quit"}:
            break
        # Simula uma fala já com wake word, como se o mic tivesse ouvido.
        await bus.publish(SpeechDetected(text=text.strip(), is_final=True, wake=True))


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
