"""Testes do OcrService: cache por assinatura, fallback e ausência de motor."""

from jarvis_sense.core.config import get_settings
from jarvis_sense.ocr.services import OcrService


class FakeOCR:
    def __init__(self, name: str, available: bool, text: str) -> None:
        self.name = name
        self._available = available
        self._text = text
        self.calls = 0

    async def is_available(self) -> bool:
        return self._available

    async def extract(self, png: bytes) -> str:
        self.calls += 1
        return self._text


async def test_uses_primary_and_caches() -> None:
    primary = FakeOCR("rapid", True, "olá mundo")
    svc = OcrService(get_settings(), primary=primary, fallback=FakeOCR("tess", True, "x"))

    sig = b"assinatura-1"
    assert await svc.extract(b"png", cache_key=sig) == "olá mundo"
    assert await svc.extract(b"png", cache_key=sig) == "olá mundo"
    assert primary.calls == 1  # segunda veio do cache


async def test_falls_back_when_primary_unavailable() -> None:
    primary = FakeOCR("rapid", False, "nope")
    fallback = FakeOCR("tess", True, "do fallback")
    svc = OcrService(get_settings(), primary=primary, fallback=fallback)

    assert await svc.extract(b"png") == "do fallback"
    assert svc.engine_name == "tess"


async def test_no_engine_returns_empty() -> None:
    svc = OcrService(
        get_settings(),
        primary=FakeOCR("rapid", False, ""),
        fallback=FakeOCR("tess", False, ""),
    )
    assert await svc.extract(b"png") == ""


async def test_cache_is_lru_bounded() -> None:
    primary = FakeOCR("rapid", True, "t")
    svc = OcrService(get_settings(), primary=primary, fallback=FakeOCR("f", True, "t"), cache_size=2)

    await svc.extract(b"a", cache_key=b"k1")
    await svc.extract(b"b", cache_key=b"k2")
    await svc.extract(b"c", cache_key=b"k3")  # expulsa k1
    await svc.extract(b"a", cache_key=b"k1")  # k1 reprocessa

    assert primary.calls == 4
