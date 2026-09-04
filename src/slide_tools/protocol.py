"""Protocolo JSON v1.2 para comunicación entre Clientes, Daemon y Extensión de Google Slides."""

from enum import Enum
import json
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


PROTOCOL_VERSION = "1.2"


class Source(str, Enum):
    ANDROID = "android"
    HARDWARE = "hardware"
    DAEMON = "daemon"
    EXTENSION = "extension"
    CLIENT = "client"


class MessageType(str, Enum):
    COMMAND = "command"
    STATE = "state"
    EVENT = "event"
    ACK = "ack"
    ERROR = "error"


class Action(str, Enum):
    # Comandos
    NEXT_SLIDE = "NEXT_SLIDE"
    PREV_SLIDE = "PREV_SLIDE"
    FIRST_SLIDE = "FIRST_SLIDE"
    LAST_SLIDE = "LAST_SLIDE"
    GO_TO_SLIDE = "GO_TO_SLIDE"
    TOGGLE_BLACKOUT = "TOGGLE_BLACKOUT"
    TOGGLE_WHITEOUT = "TOGGLE_WHITEOUT"
    TOGGLE_LASER = "TOGGLE_LASER"
    TIMER_RESET = "TIMER_RESET"
    TIMER_TOGGLE_PAUSE = "TIMER_TOGGLE_PAUSE"
    GET_STATE = "GET_STATE"
    PAIR_REQUEST = "PAIR_REQUEST"
    UNPAIR_CLIENT = "UNPAIR_CLIENT"

    # Eventos y Telemetría
    STATE_SYNC = "STATE_SYNC"
    PAIRING_REQUIRED = "PAIRING_REQUIRED"
    PAIRING_SUCCESS = "PAIRING_SUCCESS"
    COMMAND_ACK = "COMMAND_ACK"
    CLIENT_CONNECTED = "CLIENT_CONNECTED"
    CLIENT_DISCONNECTED = "CLIENT_DISCONNECTED"


class ErrorCode(str, Enum):
    ERR_PAIRING_REQUIRED = "ERR_PAIRING_REQUIRED"
    ERR_INVALID_PIN = "ERR_INVALID_PIN"
    ERR_NOT_PRESENTING = "ERR_NOT_PRESENTING"
    ERR_INVALID_SLIDE = "ERR_INVALID_SLIDE"
    ERR_INVALID_COMMAND = "ERR_INVALID_COMMAND"
    ERR_TIMEOUT = "ERR_TIMEOUT"
    ERR_MALFORMED_MESSAGE = "ERR_MALFORMED_MESSAGE"
    ERR_EXTENSION_DISCONNECTED = "ERR_EXTENSION_DISCONNECTED"


class TimerData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    elapsedSeconds: int = 0
    formattedTime: str = "00:00"
    isPaused: bool = False


class SpeakerNotesData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hasNotes: bool = False
    currentSlideNotes: str = ""


class StateSyncPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    presentationTitle: str = ""
    isPresenting: bool = False
    presentationMode: str = "standard"  # presenter_view, standard, edit
    currentSlide: int = 1
    totalSlides: int = 1
    isBlackout: bool = False
    isWhiteout: bool = False
    isLaserActive: bool = False
    timer: TimerData = Field(default_factory=TimerData)
    speakerNotes: SpeakerNotesData = Field(default_factory=SpeakerNotesData)
    connectedClients: int = 0
    pin: str = ""
    pairingUri: Optional[str] = None
    qrSvg: Optional[str] = None


class PairRequestPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pin: str
    deviceType: str = "android"  # android, hardware, cli
    clientName: Optional[str] = None


class GoToSlidePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slideNumber: int = Field(ge=1)


class Message(BaseModel):
    """Estructura de paquete JSON over WebSocket según especificación v1.2."""
    model_config = ConfigDict(extra="allow", use_enum_values=True)

    version: str = PROTOCOL_VERSION
    sessionId: str = "default"
    source: Source
    type: MessageType
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "Message":
        data = json.loads(raw)
        return cls(**data)

    @classmethod
    def command(
        cls,
        action: Action | str,
        payload: Optional[Dict[str, Any]] = None,
        source: Source = Source.CLIENT,
        session_id: str = "default"
    ) -> "Message":
        act = action.value if isinstance(action, Action) else action
        return cls(
            version=PROTOCOL_VERSION,
            sessionId=session_id,
            source=source,
            type=MessageType.COMMAND,
            action=act,
            payload=payload or {}
        )

    @classmethod
    def state_sync(
        cls,
        state: StateSyncPayload | Dict[str, Any],
        source: Source = Source.DAEMON,
        session_id: str = "default"
    ) -> "Message":
        p = state.model_dump() if isinstance(state, StateSyncPayload) else state
        return cls(
            version=PROTOCOL_VERSION,
            sessionId=session_id,
            source=source,
            type=MessageType.STATE,
            action=Action.STATE_SYNC.value,
            payload=p
        )

    @classmethod
    def ack(
        cls,
        action: str,
        status: str = "ok",
        details: Optional[str] = None,
        source: Source = Source.DAEMON,
        session_id: str = "default",
        extra: Optional[Dict[str, Any]] = None
    ) -> "Message":
        p = {"action": action, "status": status}
        if details:
            p["details"] = details
        if extra:
            p.update(extra)
        return cls(
            version=PROTOCOL_VERSION,
            sessionId=session_id,
            source=source,
            type=MessageType.ACK,
            action=Action.COMMAND_ACK.value,
            payload=p
        )

    @classmethod
    def error(
        cls,
        reason: str,
        code: ErrorCode | str,
        source: Source = Source.DAEMON,
        session_id: str = "default"
    ) -> "Message":
        c_val = code.value if isinstance(code, ErrorCode) else code
        return cls(
            version=PROTOCOL_VERSION,
            sessionId=session_id,
            source=source,
            type=MessageType.ERROR,
            action="ERROR",
            payload={"reason": reason, "code": c_val}
        )
