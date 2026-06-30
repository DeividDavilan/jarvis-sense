"""Wake word ACÚSTICA — `IWakeWord`.

Detecta a palavra de ativação direto no áudio cru, com um modelo local leve
(openWakeWord), **antes** de qualquer STT. Vantagem sobre a detecção textual
(`wake_word.WakeWordDetector`): não precisa transcrever tudo — só o comando dito
*depois* do gatilho vai para o Whisper. Mais eficiente e natural.

**Personalizável** (`JARVIS_WAKE_MODEL`):
- um nome pré-treinado: `hey_jarvis`, `alexa`, `hey_mycroft`, `hey_rhasspy`…;
- um caminho para um modelo seu (`.onnx`/`.tflite`) treinado no openWakeWord —
  ex.: `models/penelopo.onnx` (relativo à raiz do projeto);
- vários gatilhos ao mesmo tempo, separados por vírgula:
  `hey_jarvis, models/penelopo.onnx`.

- `OpenWakeWord`: implementação real.
- `NullWakeWord`: nunca dispara (acústica indisponível → cai para o modo textual).

openWakeWord é importado preguiçosamente; sem ele, `is_available()` é False.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..core.config import PROJECT_ROOT, Settings
from ..core.logging import get_logger
from ..microphone.vad import SAMPLE_RATE

logger = get_logger("Speech")

# openWakeWord foi validado com janelas de 1280 amostras (80 ms @ 16 kHz).
CHUNK_SAMPLES = 1280
CHUNK_BYTES = CHUNK_SAMPLES * 2  # int16


# --- funções puras (testáveis sem a lib) --------------------------------------

def parse_wake_models(raw: str, root: Path = PROJECT_ROOT) -> list[str]:
    """Resolve a config `wake_model` numa lista de modelos.

    Entradas que parecem caminho (terminam em .onnx/.tflite ou têm separador) são
    resolvidas para caminho absoluto (relativo à raiz do projeto, se preciso);
    as demais são tratadas como nomes pré-treinados e passam adiante.
    """
    items = [x.strip() for x in (raw or "").split(",") if x.strip()]
    resolved: list[str] = []
    for item in items:
        low = item.lower()
        looks_like_path = low.endswith((".onnx", ".tflite")) or "/" in item or "\\" in item
        if looks_like_path:
            path = Path(item)
            if not path.is_absolute():
                path = root / item
            resolved.append(str(path))
        else:
            resolved.append(item)
    return resolved or ["hey_jarvis"]


def infer_framework(models: list[str]) -> str:
    """openWakeWord usa um único framework por instância. Se algum modelo é
    .tflite, usa tflite; caso contrário, onnx (recomendado, já temos onnxruntime)."""
    return "tflite" if any(m.lower().endswith(".tflite") for m in models) else "onnx"


# --- interface ----------------------------------------------------------------

@runtime_checkable
class IWakeWord(Protocol):
    """Detector acústico de wake word, alimentado por quadros de áudio cru."""

    name: str

    async def is_available(self) -> bool:
        ...

    def process(self, frame: bytes) -> bool:
        """Recebe um quadro PCM 16 kHz int16 e devolve True quando a wake word é
        detectada. Mantém estado interno entre chamadas."""
        ...

    def reset(self) -> None:
        ...


class NullWakeWord:
    """Detector que nunca dispara (acústica desligada)."""

    name = "none"

    async def is_available(self) -> bool:
        return False

    def process(self, frame: bytes) -> bool:  # noqa: ARG002
        return False

    def reset(self) -> None:
        pass


class OpenWakeWord:
    """Implementa `IWakeWord` com o openWakeWord (um ou mais modelos)."""

    name = "openwakeword"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._models = parse_wake_models(settings.wake_model)
        self._framework = (settings.wake_framework or "").lower() or infer_framework(self._models)
        self._model = None
        self._keys: list[str] = []
        self._buf = b""
        # Última pontuação observada (para calibração no utilitário de wake word).
        self.last_score = 0.0
        self.last_name = ""
        # Cooldown pós-detecção (evita disparos repetidos no mesmo gatilho).
        self._cooldown_chunks = 0
        self._cooldown_after = max(1, int(1.5 * SAMPLE_RATE / CHUNK_SAMPLES))  # ~1,5 s

    async def is_available(self) -> bool:
        try:
            import openwakeword  # noqa: F401
        except ImportError:
            return False
        # Caminhos customizados precisam existir.
        for m in self._models:
            if (m.endswith(".onnx") or m.endswith(".tflite")) and not Path(m).exists():
                logger.warning("Modelo de wake word não encontrado: %s", m)
                return False
        try:
            self._ensure_model()
        except Exception as exc:  # noqa: BLE001 — modelo pode faltar/baixar
            logger.warning("openWakeWord indisponível: %s", exc)
            return False
        return True

    def _ensure_model(self):
        if self._model is None:
            from openwakeword.model import Model

            logger.info(
                "Carregando wake word acústica: %s (%s)…",
                ", ".join(self._models),
                self._framework,
            )
            self._model = Model(
                wakeword_models=self._models, inference_framework=self._framework
            )
            self._keys = list(self._model.models.keys())
            logger.info("Gatilhos ativos: %s", ", ".join(self._keys))
        return self._model

    def reset(self) -> None:
        self._buf = b""
        self._cooldown_chunks = 0

    def process(self, frame: bytes) -> bool:
        import numpy as np

        model = self._ensure_model()
        self._buf += frame
        fired = False
        threshold = self._settings.wake_threshold

        # Consome janelas consecutivas e não sobrepostas de 1280 amostras.
        while len(self._buf) >= CHUNK_BYTES:
            chunk, self._buf = self._buf[:CHUNK_BYTES], self._buf[CHUNK_BYTES:]
            if self._cooldown_chunks > 0:
                self._cooldown_chunks -= 1
                continue
            samples = np.frombuffer(chunk, dtype=np.int16)
            scores = model.predict(samples)
            # Dispara se QUALQUER gatilho cruzar o limiar.
            best_name, best = "", 0.0
            for key in self._keys:
                score = float(scores.get(key, 0.0))
                if score > best:
                    best_name, best = key, score
            self.last_score, self.last_name = best, best_name
            if best >= threshold:
                logger.info("Wake word '%s' detectada (score=%.2f).", best_name, best)
                self._cooldown_chunks = self._cooldown_after
                fired = True
        return fired


def create_wake_word(settings: Settings) -> IWakeWord:
    """Fábrica do detector acústico conforme o modo de wake configurado."""
    if (settings.wake_mode or "text").lower() == "acoustic":
        return OpenWakeWord(settings)
    return NullWakeWord()
