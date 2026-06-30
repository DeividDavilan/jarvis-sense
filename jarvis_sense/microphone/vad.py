"""Segmentação de fala por VAD (Voice Activity Detection).

Separa fala de silêncio em quadros de 30 ms. A classe `Segmenter` acumula
estado: recebe quadros PCM e devolve o trecho completo quando detecta o fim de
uma fala (silêncio sustentado após voz). Implementa a "detecção automática de
silêncio" e a "ativação por voz" pedidas no prompt.

Dois detectores, atrás da mesma interface (`_SpeechDetector`):
- **webrtcvad** (preferido): VAD de alta qualidade do WebRTC. Requer a lib nativa.
- **energia (numpy)**: fallback em Python puro (RMS com piso de ruído adaptativo),
  sem compilação. Garante que o microfone funcione mesmo sem o webrtcvad
  (ex.: Python muito novo sem wheel) — resiliência > dependência.

Ambos são importados preguiçosamente; a parte de lógica é testável sem eles.
"""

from __future__ import annotations

from ..core.logging import get_logger

logger = get_logger("Speech")

# webrtcvad aceita 8/16/32/48 kHz e quadros de 10/20/30 ms.
SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_BYTES = int(SAMPLE_RATE * (FRAME_MS / 1000.0)) * 2  # int16 → 2 bytes/amostra


class _WebrtcDetector:
    """Detector de fala usando webrtcvad (se instalado)."""

    def __init__(self, aggressiveness: int) -> None:
        import webrtcvad  # pode levantar ImportError

        self._vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame: bytes) -> bool:
        return self._vad.is_speech(frame, SAMPLE_RATE)


class _EnergyDetector:
    """Fallback: detecção por energia (RMS) com piso de ruído adaptativo.

    Sem dependência nativa (usa numpy). Marca fala quando a energia do quadro
    supera o piso de ruído de fundo por uma margem. O piso se adapta lentamente
    ao ambiente, tolerando ruído constante.
    """

    def __init__(self, margin: float = 2.5, floor_start: float = 250.0) -> None:
        self._margin = margin
        self._floor = floor_start  # piso de ruído (RMS) estimado

    def is_speech(self, frame: bytes) -> bool:
        import numpy as np

        samples = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return False
        rms = float(np.sqrt(np.mean(samples * samples)) + 1e-6)
        speech = rms > self._floor * self._margin
        if not speech:
            # Adapta o piso de ruído só no silêncio (média móvel exponencial).
            self._floor = 0.95 * self._floor + 0.05 * rms
        return speech


class Segmenter:
    """Acumula quadros e emite uma fala quando o silêncio sinaliza o fim.

    Parâmetros:
    - `aggressiveness` (0-3): agressividade do webrtcvad (ignorado no fallback).
    - `silence_ms`: silêncio contínuo que encerra uma fala.
    - `min_speech_ms`: descarta ruídos curtos (evita falsos positivos).
    """

    def __init__(
        self,
        aggressiveness: int = 2,
        silence_ms: int = 700,
        min_speech_ms: int = 250,
    ) -> None:
        self._silence_frames_limit = max(1, silence_ms // FRAME_MS)
        self._min_speech_frames = max(1, min_speech_ms // FRAME_MS)
        self._aggr = aggressiveness
        self._detector: _WebrtcDetector | _EnergyDetector | None = None
        self._reset()

    def _reset(self) -> None:
        self._voiced: list[bytes] = []
        self._silence_run = 0
        self._in_speech = False

    def _ensure_detector(self):
        if self._detector is None:
            try:
                self._detector = _WebrtcDetector(self._aggr)
                logger.info("VAD: webrtcvad (alta qualidade).")
            except ImportError:
                self._detector = _EnergyDetector()
                logger.warning("VAD: fallback por energia (webrtcvad ausente).")
        return self._detector

    def push(self, frame: bytes) -> bytes | None:
        """Processa um quadro de `FRAME_BYTES`. Retorna o PCM completo da fala
        quando ela termina, senão None."""
        if len(frame) != FRAME_BYTES:
            return None
        detector = self._ensure_detector()
        is_speech = detector.is_speech(frame)

        if is_speech:
            self._in_speech = True
            self._silence_run = 0
            self._voiced.append(frame)
            return None

        if self._in_speech:
            self._silence_run += 1
            self._voiced.append(frame)
            if self._silence_run >= self._silence_frames_limit:
                segment = b"".join(self._voiced)
                spoken_frames = len(self._voiced) - self._silence_run
                self._reset()
                if spoken_frames >= self._min_speech_frames:
                    return segment
                logger.debug("Fala curta descartada (%d quadros).", spoken_frames)
        return None
