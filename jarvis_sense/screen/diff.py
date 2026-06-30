"""Detecção de mudança entre quadros (lógica pura, sem dependências).

Recebe "assinaturas" (miniaturas em tons de cinza, como `bytes`) e calcula a
fração de pixels que mudaram acima de um limiar de intensidade. É o que evita
rodar OCR/visão em loop cego: só processamos quando a tela muda de verdade
(requisito de performance do prompt).

Trabalhar sobre `bytes` mantém isto testável sem Pillow/numpy.
"""

from __future__ import annotations

# Hash de assinatura → texto OCR, para reaproveitar resultado de telas idênticas.
SIGNATURE_BYTES_DEFAULT = 32 * 32  # miniatura 32x32 em tons de cinza


class FrameDiffer:
    """Compara a assinatura atual com a anterior e diz quanto mudou."""

    def __init__(self, pixel_threshold: int = 16) -> None:
        # Diferença mínima de intensidade (0-255) para um pixel "mudar".
        self._pixel_threshold = pixel_threshold
        self._previous: bytes | None = None

    def diff_ratio(self, signature: bytes) -> float:
        """Fração [0..1] de pixels que mudaram desde a última assinatura.

        A primeira chamada retorna 1.0 (tudo "novo"). Tamanhos divergentes
        também contam como mudança total (ex.: troca de resolução/região).
        """
        prev = self._previous
        self._previous = signature
        if prev is None or len(prev) != len(signature) or not signature:
            return 1.0
        changed = sum(
            1 for a, b in zip(prev, signature) if abs(a - b) >= self._pixel_threshold
        )
        return changed / len(signature)

    def reset(self) -> None:
        self._previous = None
