"""Serviço de OCR híbrido com cache.

`OcrService` escolhe o motor disponível (RapidOCR → Tesseract) e expõe
`extract(png, cache_key)`. O `cache_key` (a assinatura da tela) evita reprocessar
um quadro idêntico — requisito de performance ("cache inteligente", "evitar
processamento duplicado").

`create_ocr()` é a fábrica; adicionar um motor é registrá-lo aqui.
"""

from __future__ import annotations

from collections import OrderedDict

from ..core.config import Settings, get_settings
from ..core.errors import safe_async
from ..core.logging import get_logger
from .adapters.rapidocr import RapidOCREngine
from .adapters.tesseract import TesseractEngine
from .interfaces import IOCR

logger = get_logger("OCR")


def create_ocr(settings: Settings, *, engine: str | None = None) -> IOCR:
    """Cria o motor de OCR primário conforme a config."""
    choice = (engine or settings.ocr_engine).lower()
    if choice == "tesseract":
        return TesseractEngine(settings)
    return RapidOCREngine()


class OcrService:
    """Fachada de OCR com fallback automático e cache LRU por assinatura."""

    def __init__(
        self,
        settings: Settings | None = None,
        primary: IOCR | None = None,
        fallback: IOCR | None = None,
        cache_size: int = 16,
    ) -> None:
        self._settings = settings or get_settings()
        self._primary = primary or create_ocr(self._settings)
        self._fallback = fallback or TesseractEngine(self._settings)
        self._active: IOCR | None = None
        self._cache: OrderedDict[bytes, str] = OrderedDict()
        self._cache_size = cache_size

    async def _resolve(self) -> IOCR | None:
        if self._active is not None:
            return self._active
        if await self._primary.is_available():
            self._active = self._primary
        elif await self._fallback.is_available():
            logger.warning(
                "OCR '%s' indisponível; usando '%s'.", self._primary.name, self._fallback.name
            )
            self._active = self._fallback
        else:
            return None
        logger.info("OCR ativo: %s", self._active.name)
        return self._active

    @safe_async(default="", module="OCR")
    async def extract(self, png: bytes, cache_key: bytes | None = None) -> str:
        """Extrai texto do PNG. Usa cache se `cache_key` for fornecido."""
        if cache_key is not None and cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        engine = await self._resolve()
        if engine is None:
            logger.error(
                "Nenhum motor de OCR disponível. Instale rapidocr-onnxruntime "
                "(ou pytesseract + binário Tesseract)."
            )
            return ""

        text = await engine.extract(png)

        if cache_key is not None:
            self._cache[cache_key] = text
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)  # descarta o mais antigo (LRU)
        return text

    @property
    def engine_name(self) -> str:
        return self._active.name if self._active else "indisponível"
