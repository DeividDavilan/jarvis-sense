"""Adaptador OCR fallback: **Tesseract** (via pytesseract).

Requer o binário Tesseract instalado no sistema (e o idioma `por`). Configure o
caminho com `JARVIS_TESSERACT_CMD` se não estiver no PATH. Usado quando o
RapidOCR não está disponível.
"""

from __future__ import annotations

import asyncio
import io

from ...core.config import Settings
from ...core.errors import EngineUnavailableError
from ...core.logging import get_logger

logger = get_logger("OCR")


class TesseractEngine:
    name = "tesseract"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._configured = False

    async def is_available(self) -> bool:
        try:
            import pytesseract  # noqa: F401
            import PIL  # noqa: F401
        except ImportError:
            return False
        return True

    def _configure(self) -> None:
        if self._configured:
            return
        import pytesseract

        if self._settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self._settings.tesseract_cmd
        self._configured = True

    async def extract(self, png: bytes) -> str:
        return await asyncio.to_thread(self._extract_blocking, png)

    def _extract_blocking(self, png: bytes) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise EngineUnavailableError("Pacote 'pytesseract'/'Pillow' ausente.") from exc

        self._configure()
        img = Image.open(io.BytesIO(png))
        # 'por' = português; cai para o idioma padrão se o pacote não existir.
        try:
            return pytesseract.image_to_string(img, lang="por").strip()
        except pytesseract.TesseractError:
            return pytesseract.image_to_string(img).strip()
