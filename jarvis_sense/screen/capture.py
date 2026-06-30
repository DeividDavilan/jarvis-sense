"""Captura de tela real via **mss** (rápida) + **Pillow** (compressão/assinatura).

Produz um `Frame` com:
- `png`: a imagem comprimida em PNG (entrada para OCR/visão);
- `signature`: miniatura 32x32 em tons de cinza (para diff e cache).

mss/Pillow são importados preguiçosamente; sem eles, `is_available()` é False e
o módulo de visão informa o usuário (sem derrubar o sistema).
"""

from __future__ import annotations

import asyncio
import io

from ..core.logging import get_logger
from .diff import SIGNATURE_BYTES_DEFAULT
from .models import Frame, Region

logger = get_logger("Vision")

_SIG_SIDE = 32  # miniatura 32x32 → 1024 bytes de assinatura


class MssCapture:
    """Implementa `IScreenCapture` com mss + Pillow."""

    name = "mss"

    async def is_available(self) -> bool:
        try:
            import mss  # noqa: F401
            import PIL  # noqa: F401
        except ImportError:
            return False
        return True

    async def grab(self, region: Region) -> Frame:
        return await asyncio.to_thread(self._grab_blocking, region)

    def _grab_blocking(self, region: Region) -> Frame:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            if region.is_full:
                monitor = sct.monitors[1]  # monitor primário
            else:
                monitor = {
                    "left": region.left,
                    "top": region.top,
                    "width": region.width,
                    "height": region.height,
                }
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        # PNG comprimido para OCR/visão.
        png_buf = io.BytesIO()
        img.save(png_buf, format="PNG", optimize=True)

        # Assinatura: miniatura em tons de cinza (bytes crus).
        thumb = img.convert("L").resize((_SIG_SIDE, _SIG_SIDE))
        signature = thumb.tobytes()
        assert len(signature) == SIGNATURE_BYTES_DEFAULT

        return Frame(
            png=png_buf.getvalue(),
            width=img.width,
            height=img.height,
            signature=signature,
            region=region,
        )
