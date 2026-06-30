"""Testes do VisionService com captura/OCR/visão fakes — sem tela real.
Valida: só emite eventos quando a tela muda; OCRFinished com texto; visão LLM
desligada não emite VisionUpdated; ativa emite."""

from jarvis_sense.core.config import get_settings
from jarvis_sense.core.event_types import EventName
from jarvis_sense.core.events import EventBus
from jarvis_sense.ocr.services import OcrService
from jarvis_sense.screen.models import Frame, Region
from jarvis_sense.vision.services import VisionService


def _frame(sig: bytes) -> Frame:
    return Frame(png=b"PNG", width=10, height=10, signature=sig, region=Region())


class FakeCapture:
    name = "fake"

    def __init__(self, signatures: list[bytes]) -> None:
        self._sigs = signatures
        self._i = 0

    async def is_available(self) -> bool:
        return True

    async def grab(self, region: Region) -> Frame:
        sig = self._sigs[min(self._i, len(self._sigs) - 1)]
        self._i += 1
        return _frame(sig)


class FakeOCR:
    name = "fake-ocr"

    def __init__(self, text: str) -> None:
        self._text = text

    async def is_available(self) -> bool:
        return True

    async def extract(self, png: bytes) -> str:
        return self._text


class FakeVision:
    def __init__(self, name: str, summary: str) -> None:
        self.name = name
        self._summary = summary

    async def is_available(self) -> bool:
        return True

    async def describe(self, png: bytes, ocr_text: str) -> str:
        return self._summary


def _service(bus, capture, ocr_text="texto da tela", vision=None):
    return VisionService(
        get_settings(),
        bus,
        capture=capture,
        ocr=OcrService(get_settings(), primary=FakeOCR(ocr_text), fallback=FakeOCR("")),
        vision=vision or FakeVision("off", ""),
    )


async def test_no_change_emits_nothing() -> None:
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe_all(lambda e: seen.append(e.name.value))

    sig = bytes([10] * 1024)
    svc = _service(bus, FakeCapture([sig, sig]))
    await svc._tick()   # primeiro frame = mudança total → emite
    seen.clear()
    await svc._tick()   # igual ao anterior → nada

    assert seen == []


async def test_change_emits_screen_and_ocr() -> None:
    bus = EventBus()
    names: list[str] = []
    bus.subscribe_all(lambda e: names.append(e.name.value))

    svc = _service(bus, FakeCapture([bytes([0] * 1024)]))
    await svc._tick()

    assert EventName.SCREEN_CHANGED.value in names
    assert EventName.OCR_FINISHED.value in names
    assert EventName.VISION_UPDATED.value not in names  # visão desligada


async def test_vision_enabled_emits_vision_updated() -> None:
    bus = EventBus()
    summaries: list[str] = []
    bus.subscribe(EventName.VISION_UPDATED, lambda e: summaries.append(e.summary))

    svc = _service(bus, FakeCapture([bytes([0] * 1024)]), vision=FakeVision("anthropic", "É o VS Code."))
    await svc._tick()

    assert summaries == ["É o VS Code."]
