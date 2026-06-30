"""Utilitário da wake word acústica.

    python -m jarvis_sense.speech.wake_demo            # lista modelos + calibra ao vivo
    python -m jarvis_sense.speech.wake_demo --list     # só lista os pré-treinados

No modo ao vivo, abre o microfone e mostra a pontuação do(s) gatilho(s)
configurado(s) em `JARVIS_WAKE_MODEL` em tempo real — diga "hey jarvis" (ou o seu
modelo) e veja o score subir. Útil para escolher o `JARVIS_WAKE_THRESHOLD`.
"""

from __future__ import annotations

import asyncio
import os
import sys

from ..core.config import get_settings
from ..microphone.services import MicrophoneSource
from .acoustic import OpenWakeWord


def list_pretrained() -> list[str]:
    """Nomes dos modelos pré-treinados baixados pelo openWakeWord."""
    try:
        import openwakeword as o
    except ImportError:
        return []
    models_dir = os.path.join(os.path.dirname(o.__file__), "resources", "models")
    if not os.path.isdir(models_dir):
        return []
    names = {
        os.path.splitext(f)[0]
        for f in os.listdir(models_dir)
        if f.endswith((".onnx", ".tflite"))
    }
    # Remove os modelos internos (features/VAD), que não são wake words.
    internal = {"melspectrogram", "embedding_model", "silero_vad"}
    return sorted(n for n in names if n not in internal)


async def _live() -> None:
    settings = get_settings()
    detector = OpenWakeWord(settings)
    if not await detector.is_available():
        print("openWakeWord/modelo indisponível. Veja docs/WAKE_WORD.md.")
        return
    source = MicrophoneSource(settings)
    if not await source.is_available():
        print("Microfone indisponível (instale sounddevice).")
        return

    print(
        f"Calibrando '{settings.wake_model}' (limiar={settings.wake_threshold}). "
        "Fale o gatilho; Ctrl+C para sair.\n"
    )
    async for frame in source.frames():
        fired = detector.process(frame)
        bar = "#" * int(detector.last_score * 30)
        sys.stdout.write(f"\r{detector.last_name:<14} [{bar:<30}] {detector.last_score:0.2f} ")
        sys.stdout.flush()
        if fired:
            print(f"\n>>> GATILHO! '{detector.last_name}' detectado.\n")


def main() -> None:
    print("Modelos de wake word pré-treinados disponíveis:")
    for name in list_pretrained() or ["(nenhum — rode download_models)"]:
        print(f"  - {name}")
    print()
    if "--list" in sys.argv:
        return
    try:
        asyncio.run(_live())
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    main()
