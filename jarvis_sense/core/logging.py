"""Logging por módulo. Cada módulo (Audio, OCR, Speech, Vision, Automation,
Bridge, Brain...) recebe seu próprio logger nomeado, com saída no console e em
um arquivo dedicado sob `jarvis-sense/logs/<modulo>.log`.

Níveis suportados: DEBUG, INFO, WARNING, ERROR. O nível global vem de
`Settings.log_level`. Use sempre `get_logger("Modulo")` em vez de
`print()` — assim os requisitos de "logs completos, separados por módulo e por
nível" do prompt são atendidos de forma uniforme.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import LOG_DIR, get_settings

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-12s | %(message)s"
_DATEFMT = "%H:%M:%S"
_configured: set[str] = set()


def _enable_utf8_console() -> None:
    """Garante saída UTF-8 no console do Windows (cp1252 não cobre todos os
    caracteres). Idempotente e tolerante a ambientes sem stdout reconfigurável."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


_enable_utf8_console()


def get_logger(module: str) -> logging.Logger:
    """Retorna (criando na primeira vez) um logger para `module`.

    O logger escreve no console e em `logs/<module>.log` (rotativo, 1 MB x3).
    Chamadas repetidas com o mesmo nome retornam o mesmo logger configurado.
    """
    name = module.strip() or "Jarvis"
    logger = logging.getLogger(name)
    if name in _configured:
        return logger

    level = getattr(logging, get_settings().log_level.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_DIR / f"{name.lower()}.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Se o disco/permissão falhar, seguimos só com o console — logging nunca
        # pode derrubar a aplicação.
        logger.warning("Não foi possível abrir arquivo de log; usando só console.")

    _configured.add(name)
    return logger
