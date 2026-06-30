"""Demo da voz do Jarvis.

    python -m jarvis_sense.tts.demo
    python -m jarvis_sense.tts.demo "frase personalizada"

Fala a frase em pt-BR usando o motor configurado (edge por padrão; cai para
SAPI offline se o edge-tts não estiver instalado/sem internet).
"""

from __future__ import annotations

import asyncio
import sys

from ..core.config import get_settings
from .services import TTSService


async def _main(text: str) -> None:
    service = TTSService(get_settings())
    print(f"[Jarvis fala] {text}")
    await service.speak(text)


def main() -> None:
    text = " ".join(sys.argv[1:]) or "Sistemas online, senhor. Jarvis ao seu dispor."
    asyncio.run(_main(text))


if __name__ == "__main__":
    main()
