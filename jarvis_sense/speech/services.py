"""Serviço de entrada de voz — os "ouvidos" do Jarvis.

`VoiceInputService` é um `Service` (laço de longa duração) que compõe uma
`IAudioSource` (microfone), um `ISTT` híbrido (Groq Whisper padrão, faster-whisper
fallback) e a detecção da wake word, publicando `OnSpeechDetected` no barramento.

Dois modos de ativação (config `JARVIS_WAKE_MODE`):

- **acoustic** (padrão): um detector acústico (`IWakeWord`/openWakeWord) escuta o
  áudio cru e dispara ao ouvir "hey jarvis"; só então a fala seguinte é capturada
  e transcrita. Eficiente — não transcreve o que não é comando. Cai para `text`
  se o openWakeWord/modelo não estiver disponível.
- **text**: transcreve cada fala e detecta "jarvis" no texto (sem libs extras).

Não conhece o cérebro nem o TTS — só publica eventos (desacoplamento total).
Assina `OnJarvisSpeaking` para silenciar o microfone enquanto o Jarvis fala
(anti-eco), atendendo o requisito de voz única.
"""

from __future__ import annotations

from ..core.config import Settings, get_settings
from ..core.errors import safe_async
from ..core.event_types import ControlCommand, EventName, MicStateChanged, SpeechDetected
from ..core.events import EventBus, get_event_bus
from ..core.logging import get_logger
from ..microphone.interfaces import IAudioSource
from ..microphone.services import MicrophoneSource
from ..microphone.models import Utterance
from ..microphone.vad import FRAME_MS, SAMPLE_RATE, Segmenter
from .acoustic import IWakeWord, create_wake_word
from .config import create_fallback_stt, create_stt
from .interfaces import ISTT
from .wake_word import WakeWordDetector

logger = get_logger("Speech")

# Tempo máximo aguardando o comando após a wake word acústica (volta a "ocioso").
COMMAND_WINDOW_S = 8.0


class VoiceInputService:
    name = "voice-input"

    def __init__(
        self,
        settings: Settings | None = None,
        bus: EventBus | None = None,
        source: IAudioSource | None = None,
        stt: ISTT | None = None,
        fallback_stt: ISTT | None = None,
        wake_acoustic: IWakeWord | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._bus = bus or get_event_bus()
        self._source = source or MicrophoneSource(self._settings, self._bus)
        self._stt = stt or create_stt(self._settings)
        self._fallback = fallback_stt or create_fallback_stt(self._settings, self._stt)
        self._wake_text = WakeWordDetector(self._settings.wake_word)
        self._wake_acoustic = wake_acoustic or create_wake_word(self._settings)
        self._active_stt: ISTT | None = None
        self._enabled = True

        # Silencia o mic enquanto o Jarvis fala (anti-eco).
        self._bus.subscribe(EventName.JARVIS_SPEAKING, self._on_jarvis_speaking)
        self._bus.subscribe(EventName.CONTROL_CMD, self._on_control)

    def _on_jarvis_speaking(self, event) -> None:  # noqa: ANN001
        setter = getattr(self._source, "set_muted", None)
        if callable(setter):
            setter(bool(event.speaking))

    def _on_control(self, event: ControlCommand) -> None:
        if event.module != "mic":
            return
        if event.action == "enable":
            self._enabled = True
        elif event.action == "disable":
            self._enabled = False
        else:
            self._enabled = not self._enabled
        logger.info("Microfone %s.", "habilitado" if self._enabled else "desabilitado")

    async def _resolve_stt(self) -> ISTT:
        if self._active_stt is not None:
            return self._active_stt
        if await self._stt.is_available():
            self._active_stt = self._stt
        elif await self._fallback.is_available():
            logger.warning(
                "STT '%s' indisponível; usando fallback '%s'.",
                self._stt.name,
                self._fallback.name,
            )
            self._active_stt = self._fallback
        else:
            logger.error("Nenhum motor de STT disponível.")
            self._active_stt = self._stt  # tentará e falhará com log
        logger.info("STT ativo: %s", self._active_stt.name)
        return self._active_stt

    async def run(self) -> None:
        """Escolhe o modo de ativação e roda o laço correspondente."""
        if not await self._source.is_available():
            logger.error(
                "Microfone indisponível. Instale: sounddevice numpy "
                "(webrtcvad é opcional — sem ele, usa-se VAD por energia). "
                "Serviço de voz inativo."
            )
            return

        await self._bus.publish(MicStateChanged(state="idle"))

        if (self._settings.wake_mode or "text").lower() == "acoustic":
            if await self._wake_acoustic.is_available():
                logger.info("Modo de ativação: ACÚSTICO (%s).", self._wake_acoustic.name)
                await self._run_acoustic()
                return
            logger.warning(
                "Wake word acústica indisponível (instale 'openwakeword'); "
                "usando modo textual."
            )
        else:
            logger.info("Modo de ativação: TEXTUAL.")
        await self._run_text()

    # --- modo textual ----------------------------------------------------------
    async def _run_text(self) -> None:
        async for utterance in self._source.utterances():
            await self._handle_text(utterance)

    @safe_async(module="Speech")
    async def _handle_text(self, utterance: Utterance) -> None:
        stt = await self._resolve_stt()
        text = (await stt.transcribe(utterance)).strip()
        if not text:
            return
        found, command = self._wake_text.detect(text)
        logger.info("Ouvi: %r (wake=%s)", text, found)
        await self._bus.publish(
            SpeechDetected(text=command if found else text, is_final=True, wake=found)
        )

    # --- modo acústico ---------------------------------------------------------
    async def _run_acoustic(self) -> None:
        """Máquina de estados: OCIOSO escuta a wake word; ESCUTANDO captura o
        comando seguinte (VAD) e o transcreve."""
        segmenter = Segmenter()
        listening = False
        window_frames = 0
        max_frames = int(COMMAND_WINDOW_S * 1000 / FRAME_MS)

        async for frame in self._source.frames():
            if not self._enabled:
                continue

            if not listening:
                if self._wake_acoustic.process(frame):
                    # Gatilho: confirma e abre janela de comando. O cérebro
                    # responde "Sim, senhor?" e passa a aceitar a próxima fala.
                    await self._bus.publish(MicStateChanged(state="wake_triggered"))
                    await self._bus.publish(SpeechDetected(text="", is_final=True, wake=True))
                    listening = True
                    window_frames = 0
                    segmenter = Segmenter()
                continue

            # ESCUTANDO o comando.
            await self._bus.publish(MicStateChanged(state="command_listening"))
            window_frames += 1
            segment = segmenter.push(frame)
            if segment:
                await self._handle_command(Utterance(pcm=segment, sample_rate=SAMPLE_RATE))
                listening = False
                self._wake_acoustic.reset()  # descarta buffer residual
                await self._bus.publish(MicStateChanged(state="idle"))
            elif window_frames >= max_frames:
                logger.info("Tempo de comando esgotado; voltando a ouvir a wake word.")
                listening = False
                self._wake_acoustic.reset()
                await self._bus.publish(MicStateChanged(state="idle"))

    @safe_async(module="Speech")
    async def _handle_command(self, utterance: Utterance) -> None:
        """Transcreve o comando captado após a wake word acústica e o publica.

        Sai com `wake=False`: o cérebro já está na janela de conversa (aberta pelo
        evento de wake), então processa a fala normalmente."""
        stt = await self._resolve_stt()
        text = (await stt.transcribe(utterance)).strip()
        if not text:
            return
        logger.info("Comando após wake: %r", text)
        await self._bus.publish(SpeechDetected(text=text, is_final=True, wake=False))
