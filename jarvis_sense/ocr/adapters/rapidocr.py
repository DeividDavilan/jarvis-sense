"""Adaptador OCR primário: **RapidOCR** (ONNX, gratuito e self-contained).

Não exige binário de sistema (ao contrário do Tesseract): traz seus próprios
modelos ONNX. Decodifica o PNG com Pillow → numpy e roda o reconhecimento.
O motor é carregado preguiçosamente (custa alguns segundos na primeira vez).
"""

from __future__ import annotations

import asyncio
import io

from ...core.errors import EngineUnavailableError
from ...core.logging import get_logger

logger = get_logger("OCR")


class RapidOCREngine:
    name = "rapidocr"

    def __init__(self) -> None:
        self._engine = None

    async def is_available(self) -> bool:
        try:
            import rapidocr_onnxruntime  # noqa: F401
            import PIL  # noqa: F401
            import numpy  # noqa: F401
        except ImportError:
            return False
        return True

    def _ensure_engine(self):
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as exc:
                raise EngineUnavailableError("Pacote 'rapidocr-onnxruntime' ausente.") from exc
            logger.info("Carregando RapidOCR (ONNX)…")
            self._engine = RapidOCR()
        return self._engine

    async def extract(self, png: bytes) -> str:
        return await asyncio.to_thread(self._extract_blocking, png)

    def _extract_blocking(self, png: bytes) -> str:
        import numpy as np
        from PIL import Image

        engine = self._ensure_engine()
        img = Image.open(io.BytesIO(png)).convert("RGB")
        result, _elapsed = engine(np.array(img))
        if not result:
            return ""
        # result = lista de [box, texto, score]; concatenamos os textos.
        return "\n".join(line[1] for line in result).strip()
