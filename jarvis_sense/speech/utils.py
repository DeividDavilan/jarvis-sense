"""Utilitários de STT: empacotar PCM em WAV na memória (sem libs externas)."""

from __future__ import annotations

import io
import wave

from ..microphone.models import Utterance


def utterance_to_wav_bytes(utterance: Utterance) -> bytes:
    """Converte PCM mono int16 em um arquivo WAV completo (bytes), usando apenas
    a stdlib (`wave`). Formato aceito por APIs de transcrição (ex.: Groq Whisper).
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # int16
        wav.setframerate(utterance.sample_rate)
        wav.writeframes(utterance.pcm)
    return buffer.getvalue()
