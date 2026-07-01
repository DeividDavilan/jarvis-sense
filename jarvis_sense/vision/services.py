"""Serviço de visão — os "olhos" do Jarvis.

`VisionService` é um `Service` (laço) que orquestra o pipeline de percepção
visual, de forma econômica:

    a cada `screen_interval`s:
        captura um quadro (mss)
        calcula o diff vs. o quadro anterior
        SE mudou acima do limiar:
            publica OnScreenChanged
            roda OCR (com cache por assinatura)  → publica OnOCRFinished
            SE visão LLM ativa: descreve a tela  → publica OnVisionUpdated

Assim o OCR/visão só rodam quando a tela muda de fato (requisitos de performance:
diff de frames, cache, sem processamento cego). Os módulos screen/ocr/vision não
se conhecem — esta classe é o ponto de composição.
"""

from __future__ import annotations

import asyncio

from ..core.config import Settings, get_settings
from ..core.errors import safe_async
from ..core.event_types import BrainThinking, ControlCommand, EventName, OCRFinished, ScreenChanged, VisionUpdated
from ..core.events import EventBus, get_event_bus
from ..core.logging import get_logger
from ..ocr.services import OcrService
from ..screen.capture import MssCapture
from ..screen.diff import FrameDiffer
from ..screen.interfaces import IScreenCapture
from ..screen.models import Region
from .config import create_vision
from .interfaces import IVision

logger = get_logger("Vision")

CHANGE_THRESHOLD = 0.02  # 2% dos pixels mudaram → reprocessa


class VisionService:
    name = "vision"

    def __init__(
        self,
        settings: Settings | None = None,
        bus: EventBus | None = None,
        capture: IScreenCapture | None = None,
        ocr: OcrService | None = None,
        vision: IVision | None = None,
        region: Region | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._bus = bus or get_event_bus()
        self._capture = capture or MssCapture()
        self._ocr = ocr or OcrService(self._settings)
        self._vision = vision or create_vision(self._settings)
        self._region = region or Region()
        self._differ = FrameDiffer()
        self._ocr_enabled = True
        self._vision_enabled = True
        self._paused = False  # pausado enquanto o cérebro consulta a LLM local
        self._bus.subscribe(EventName.CONTROL_CMD, self._on_control)
        self._bus.subscribe(EventName.BRAIN_THINKING, self._on_brain_thinking)

    def _on_brain_thinking(self, event: BrainThinking) -> None:
        # Em CPUs fracas, OCR + LLM local competindo por núcleo pode
        # desacelerar (ou travar) a resposta do Ollama — pausa o tick
        # enquanto o cérebro está consultando o LLM.
        self._paused = event.thinking
        if self._paused:
            logger.debug("Visão pausada (cérebro consultando LLM).")
        else:
            logger.debug("Visão retomada.")

    def _on_control(self, event: ControlCommand) -> None:
        def _toggle(current: bool, action: str) -> bool:
            if action == "enable":
                return True
            if action == "disable":
                return False
            return not current

        if event.module == "vision":
            self._vision_enabled = _toggle(self._vision_enabled, event.action)
            logger.info("Visão LLM %s.", "ativada" if self._vision_enabled else "desativada")
        elif event.module == "ocr":
            self._ocr_enabled = _toggle(self._ocr_enabled, event.action)
            logger.info("OCR %s.", "ativado" if self._ocr_enabled else "desativado")

    async def run(self) -> None:
        if not await self._capture.is_available():
            logger.error(
                "Captura de tela indisponível. Instale: mss, Pillow. "
                "Serviço de visão inativo."
            )
            return
        logger.info(
            "Visão online (OCR=%s, visão-LLM=%s, intervalo=%.1fs).",
            self._settings.ocr_engine,
            self._vision.name,
            self._settings.screen_interval,
        )
        while True:
            await self._tick()
            await asyncio.sleep(self._settings.screen_interval)

    @safe_async(module="Vision")
    async def _tick(self) -> None:
        if self._paused:
            return
        frame = await self._capture.grab(self._region)
        ratio = self._differ.diff_ratio(frame.signature)
        if ratio < CHANGE_THRESHOLD:
            return  # tela praticamente igual → nada a fazer

        await self._bus.publish(ScreenChanged(region=self._region.label, diff_ratio=ratio))

        text = ""
        if self._ocr_enabled:
            text = await self._ocr.extract(frame.png, cache_key=frame.signature)
            if text:
                await self._bus.publish(
                    OCRFinished(text=text, region=self._region.label, engine=self._ocr.engine_name)
                )
                logger.info("OCR (%s): %d caracteres lidos.", self._ocr.engine_name, len(text))

        if self._vision_enabled:
            summary = await self._vision.describe(frame.png, text)
            if summary:
                await self._bus.publish(VisionUpdated(summary=summary, text=text))
                logger.info("Visão: %s", summary)
