"""Testes do VoiceInputService nos dois modos, com fontes e STT fakes (sem
hardware). Modo textual: transcreve tudo + wake textual. Modo acústico: wake
word dispara antes do STT e só o comando seguinte é transcrito."""

from collections.abc import AsyncIterator

from jarvis_sense.core.config import get_settings
from jarvis_sense.core.event_types import EventName, JarvisSpeaking, SpeechDetected
from jarvis_sense.core.events import EventBus
from jarvis_sense.microphone.models import Utterance
from jarvis_sense.microphone.vad import FRAME_BYTES
from jarvis_sense.speech.acoustic import NullWakeWord
from jarvis_sense.speech.services import VoiceInputService
from jarvis_sense.speech.utils import utterance_to_wav_bytes


class FakeSource:
    """Fonte fake. `utterances()` para o modo textual; `frames()` para o acústico."""

    name = "fake"

    def __init__(self, n_utterances: int = 0, frames: list[bytes] | None = None) -> None:
        self._n = n_utterances
        self._frames = frames or []
        self.muted = False

    def set_muted(self, muted: bool) -> None:
        self.muted = muted

    async def is_available(self) -> bool:
        return True

    async def utterances(self) -> AsyncIterator[Utterance]:
        for _ in range(self._n):
            yield Utterance(pcm=b"\x00\x00" * 1600, sample_rate=16000)

    async def frames(self) -> AsyncIterator[bytes]:
        for f in self._frames:
            yield f


class FakeSTT:
    name = "fake-stt"

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    async def is_available(self) -> bool:
        return True

    async def transcribe(self, _utterance: Utterance) -> str:
        self.calls += 1
        return self._text


class FakeAcoustic:
    """Wake word acústica fake: dispara quando recebe um quadro 'marcador'."""

    name = "fake-acoustic"

    def __init__(self) -> None:
        self.resets = 0

    async def is_available(self) -> bool:
        return True

    def process(self, frame: bytes) -> bool:
        return frame[:4] == b"WAKE"

    def reset(self) -> None:
        self.resets += 1


def _silence_frame() -> bytes:
    return b"\x00" * FRAME_BYTES


def _wake_frame() -> bytes:
    return b"WAKE" + b"\x00" * (FRAME_BYTES - 4)


def test_wav_roundtrip_header() -> None:
    wav = utterance_to_wav_bytes(Utterance(pcm=b"\x01\x00" * 100, sample_rate=16000))
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"


# --- modo textual (wake acústica desligada via NullWakeWord) -------------------

async def test_text_mode_publishes_with_wake() -> None:
    bus = EventBus()
    events: list[SpeechDetected] = []
    bus.subscribe(EventName.SPEECH_DETECTED, lambda e: events.append(e))

    svc = VoiceInputService(
        get_settings(), bus,
        source=FakeSource(n_utterances=1),
        stt=FakeSTT("Jarvis, abrir o painel"),
        fallback_stt=FakeSTT(""),
        wake_acoustic=NullWakeWord(),  # força modo textual
    )
    await svc.run()

    assert len(events) == 1
    assert events[0].wake is True
    assert events[0].text == "abrir o painel"


async def test_anti_echo_mutes_microphone_when_jarvis_speaks() -> None:
    bus = EventBus()
    source = FakeSource()
    VoiceInputService(
        get_settings(), bus, source=source,
        stt=FakeSTT(""), fallback_stt=FakeSTT(""), wake_acoustic=NullWakeWord(),
    )

    await bus.publish(JarvisSpeaking(text="oi", speaking=True))
    assert source.muted is True
    await bus.publish(JarvisSpeaking(text="oi", speaking=False))
    assert source.muted is False


# --- modo acústico -------------------------------------------------------------

async def test_acoustic_mode_wake_then_command() -> None:
    bus = EventBus()
    events: list[SpeechDetected] = []
    bus.subscribe(EventName.SPEECH_DETECTED, lambda e: events.append(e))

    # Sequência: silêncio, WAKE, fala (alta energia), silêncio (fecha o comando).
    loud = (b"\x40\x10" * (FRAME_BYTES // 2))  # ~não-zero → energia de fala
    frames = [_silence_frame(), _wake_frame()] + [loud] * 12 + [_silence_frame()] * 30

    stt = FakeSTT("abrir o painel")
    svc = VoiceInputService(
        get_settings(), bus,
        source=FakeSource(frames=frames),
        stt=stt, fallback_stt=FakeSTT(""),
        wake_acoustic=FakeAcoustic(),
    )
    await svc._run_acoustic()

    # 1º evento: wake (texto vazio); 2º: o comando transcrito (wake=False).
    assert len(events) == 2
    assert events[0].wake is True and events[0].text == ""
    assert events[1].wake is False and events[1].text == "abrir o painel"
    assert stt.calls == 1  # só o comando foi transcrito (não o silêncio)


async def test_acoustic_mode_ignores_audio_without_wake() -> None:
    bus = EventBus()
    events: list[SpeechDetected] = []
    bus.subscribe(EventName.SPEECH_DETECTED, lambda e: events.append(e))

    loud = b"\x40\x10" * (FRAME_BYTES // 2)
    frames = [loud] * 20 + [_silence_frame()] * 20  # fala, mas nenhuma wake word

    stt = FakeSTT("não deveria transcrever")
    svc = VoiceInputService(
        get_settings(), bus,
        source=FakeSource(frames=frames),
        stt=stt, fallback_stt=FakeSTT(""),
        wake_acoustic=FakeAcoustic(),
    )
    await svc._run_acoustic()

    assert events == []
    assert stt.calls == 0  # nada transcrito sem a wake word
