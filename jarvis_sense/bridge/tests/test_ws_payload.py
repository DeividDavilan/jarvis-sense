"""Testa a serialização dos eventos para o frame JSON do WebSocket de percepção."""

import json

from jarvis_sense.core.event_types import OCRFinished, SpeechDetected


def test_event_serializes_to_json_frame() -> None:
    payload = OCRFinished(text="olá", region="full", engine="rapidocr").to_payload()
    frame = json.dumps(payload, default=str, ensure_ascii=False)
    back = json.loads(frame)
    assert back["type"] == "OnOCRFinished"
    assert back["text"] == "olá"
    assert back["engine"] == "rapidocr"


def test_speech_event_frame() -> None:
    frame = json.dumps(SpeechDetected(text="oi", wake=True).to_payload(), default=str)
    back = json.loads(frame)
    assert back["type"] == "OnSpeechDetected" and back["wake"] is True
