"""Demo de visão: captura a tela uma vez e imprime o texto lido por OCR.

    python -m jarvis_sense.vision.demo

Requer: mss, Pillow e um motor de OCR (rapidocr-onnxruntime OU pytesseract +
binário Tesseract). Útil para validar a Fase 4 sem subir o sistema inteiro.
"""

from __future__ import annotations

import asyncio

from ..core.config import get_settings
from ..ocr.services import OcrService
from ..screen.capture import MssCapture
from ..screen.models import Region


async def _main() -> None:
    settings = get_settings()
    capture = MssCapture()
    if not await capture.is_available():
        print("Captura indisponível. Instale: pip install mss Pillow")
        return

    frame = await capture.grab(Region())
    print(f"Tela capturada: {frame.width}x{frame.height}, PNG {len(frame.png)} bytes.")

    ocr = OcrService(settings)
    text = await ocr.extract(frame.png, cache_key=frame.signature)
    if not text:
        print("Nenhum texto lido (ou OCR indisponível: instale rapidocr-onnxruntime).")
        return
    print(f"\n--- Texto lido pela tela (motor: {ocr.engine_name}) ---\n{text[:1500]}")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
