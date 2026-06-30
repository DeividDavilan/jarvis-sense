"""Testes dos tipos de evento: serialização para payload e nome canônico."""

from jarvis_sense.core.event_types import EventName, JarvisSpeaking, SpeechDetected


def test_payload_includes_type_and_fields() -> None:
    payload = SpeechDetected(text="oi", wake=True).to_payload()
    assert payload["type"] == EventName.SPEECH_DETECTED.value
    assert payload["text"] == "oi"
    assert payload["wake"] is True
    assert "ts" in payload


def test_name_is_class_level_not_in_init() -> None:
    ev = JarvisSpeaking(text="falando", speaking=True)
    assert ev.name is EventName.JARVIS_SPEAKING
    # `name` é ClassVar: não aparece no payload como campo de dados além de `type`.
    assert "name" not in ev.to_payload()


def test_events_are_immutable() -> None:
    ev = SpeechDetected(text="x")
    try:
        ev.text = "y"  # type: ignore[misc]
    except Exception as exc:  # frozen → FrozenInstanceError
        assert "cannot assign" in str(exc).lower() or exc.__class__.__name__ == "FrozenInstanceError"
    else:
        raise AssertionError("evento deveria ser imutável")
