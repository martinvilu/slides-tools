import pytest
from slide_tools.protocol import (
    Action,
    ErrorCode,
    Message,
    MessageType,
    PROTOCOL_VERSION,
    PairRequestPayload,
    Source,
    SpeakerNotesData,
    StateSyncPayload,
    TimerData,
)


def test_command_serialization():
    msg = Message.command(Action.NEXT_SLIDE, source=Source.ANDROID)
    assert msg.version == PROTOCOL_VERSION
    assert msg.type == MessageType.COMMAND
    assert msg.action == "NEXT_SLIDE"
    assert msg.source == Source.ANDROID

    raw = msg.to_json()
    parsed = Message.from_json(raw)
    assert parsed.action == "NEXT_SLIDE"


def test_state_sync_payload():
    timer = TimerData(elapsedSeconds=125, formattedTime="02:05", isPaused=False)
    notes = SpeakerNotesData(hasNotes=True, currentSlideNotes="Introducción del proyecto.")
    state = StateSyncPayload(
        presentationTitle="Demo 2026",
        isPresenting=True,
        presentationMode="presenter_view",
        currentSlide=3,
        totalSlides=20,
        timer=timer,
        speakerNotes=notes,
        pin="1234"
    )

    msg = Message.state_sync(state)
    assert msg.action == "STATE_SYNC"
    assert msg.payload["currentSlide"] == 3
    assert msg.payload["timer"]["elapsedSeconds"] == 125
    assert msg.payload["speakerNotes"]["currentSlideNotes"] == "Introducción del proyecto."
    assert msg.payload["pin"] == "1234"


def test_pair_request():
    req = PairRequestPayload(pin="4821", deviceType="hardware", clientName="ESP32-Clicker")
    msg = Message.command(Action.PAIR_REQUEST, req.model_dump(), source=Source.HARDWARE)
    assert msg.payload["pin"] == "4821"
    assert msg.payload["clientName"] == "ESP32-Clicker"


def test_ack_and_error():
    ack = Message.ack("NEXT_SLIDE", status="ok", details="Avanzado a slide 4")
    assert ack.type == MessageType.ACK
    assert ack.payload["action"] == "NEXT_SLIDE"

    err = Message.error("PIN incorrecto", ErrorCode.ERR_INVALID_PIN)
    assert err.type == MessageType.ERROR
    assert err.payload["code"] == "ERR_INVALID_PIN"
