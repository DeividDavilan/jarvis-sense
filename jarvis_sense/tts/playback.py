"""Reprodução de áudio nativa do Windows, sem dependências extras.

`edge-tts` produz MP3. Em vez de exigir uma biblioteca de player (pygame,
simpleaudio, playsound...), usamos a API **MCI (winmm)** que já vem no Windows,
via `ctypes`. `play_file()` bloqueia até o áudio terminar — ideal para uma fala
síncrona, em que o microfone deve ficar mudo enquanto o Jarvis fala.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from ..core.logging import get_logger

logger = get_logger("TTS")

_mci_lock = threading.Lock()


def play_file(path: str | Path) -> None:
    """Reproduz um arquivo de áudio (mp3/wav) e bloqueia até terminar.

    Implementação Windows via MCI. Em outros SOs, registra um aviso e retorna
    (o projeto é Windows-first, mas isso evita quebrar import/test em CI Linux).
    """
    path = Path(path)
    if not path.exists():
        logger.error("Arquivo de áudio inexistente: %s", path)
        return

    if not sys.platform.startswith("win"):
        logger.warning("Reprodução MCI só no Windows; pulando em %s", sys.platform)
        return

    import ctypes

    alias = f"jarvis_tts_{threading.get_ident()}"
    # MCI exige caminho entre aspas e usa um "alias" para controlar a faixa.
    cmds = [
        f'open "{path}" type mpegvideo alias {alias}',
        f"play {alias} wait",  # 'wait' bloqueia até o fim da reprodução
        f"close {alias}",
    ]
    with _mci_lock:  # MCI não é reentrante de forma segura entre threads
        winmm = ctypes.windll.winmm
        for cmd in cmds:
            err = winmm.mciSendStringW(ctypes.c_wchar_p(cmd), None, 0, None)
            if err:
                logger.error("MCI falhou (%d) no comando: %s", err, cmd)
                # Tenta fechar para não vazar o alias.
                winmm.mciSendStringW(ctypes.c_wchar_p(f"close {alias}"), None, 0, None)
                return
