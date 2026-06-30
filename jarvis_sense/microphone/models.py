"""Modelos de dados de áudio compartilhados (microfone e loopback).

`Utterance` carrega um trecho de fala já segmentado: PCM mono 16-bit assinado
(little-endian) + taxa de amostragem. Mantemos o áudio como `bytes` puros para
não impor `numpy` a quem só consome o resultado (baixo acoplamento); os
adaptadores de STT convertem para o formato que precisarem.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Utterance:
    """Um trecho contínuo de fala detectado pela VAD."""

    pcm: bytes              # PCM mono, int16 little-endian
    sample_rate: int = 16000

    @property
    def duration_s(self) -> float:
        # 2 bytes por amostra (int16), 1 canal.
        return len(self.pcm) / 2 / self.sample_rate if self.sample_rate else 0.0
