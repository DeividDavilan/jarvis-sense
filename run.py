"""Ponto de entrada do Jarvis Sense.

Abra este projeto no Windows Terminal e rode:

    python run.py

Sobe a aplicação completa (todos os serviços ativados no composition root).
Encerre com Ctrl+C.
"""

from __future__ import annotations

import asyncio

from jarvis_sense.core.logging import get_logger
from jarvis_sense.services.app import JarvisSenseApp

logger = get_logger("Jarvis")


def main() -> None:
    app = JarvisSenseApp()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Encerrado pelo usuário.")


if __name__ == "__main__":
    main()
