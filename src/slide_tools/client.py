"""Cliente WebSocket para interactuar con SlideDaemon."""

import asyncio
import os
from typing import Any, AsyncGenerator, Dict, Optional
import websockets
from websockets.asyncio.client import connect

from cast_tools_common.reconexion import con_reintentos

from slide_tools.protocol import (
    Action,
    ErrorCode,
    Message,
    MessageType,
    Source,
    StateSyncPayload,
)


class SlideClient:
    """Cliente para control remoto y recepción de telemetría de Google Slides."""

    def __init__(
        self,
        uri: str = "ws://127.0.0.1:8766",
        pin: Optional[str] = None,
        device_type: str = "cli",
        client_name: str = "CLI-Client",
        timeout: float = 3.0,
        reintentos: int = 3,
    ):
        self.uri = uri
        self.reintentos = reintentos
        # El PIN hace falta sólo contra un daemon de otro equipo: desde el mismo equipo la
        # conexión es de confianza. Al emparejarse, el daemon devuelve un token de reconexión.
        self.pin = pin or os.environ.get("SLIDE_TOOLS_PIN") or None
        self.token: Optional[str] = None
        self.device_type = device_type
        self.client_name = client_name
        self.timeout = timeout
        self._ws: Optional[Any] = None
        self.is_paired = False
        self.latest_state: Optional[StateSyncPayload] = None

    async def connect(self) -> None:
        # Si la red del aula se cae un momento, reintenta con espera exponencial (QoL #608).
        self._ws = await con_reintentos(
            lambda: connect(self.uri, proxy=None, open_timeout=self.timeout),
            self.reintentos,
            errores=(OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException),
        )
        assert self._ws is not None
        try:
            raw_init = await asyncio.wait_for(self._ws.recv(), timeout=self.timeout)
            msg = Message.from_json(raw_init)
            if msg.action == Action.STATE_SYNC.value:
                self.latest_state = StateSyncPayload(**msg.payload)
        except Exception:
            pass

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self) -> "SlideClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def pair(self, pin: Optional[str] = None) -> bool:
        """Se empareja con el PIN indicado o, si no hay, con el token de un emparejamiento anterior."""
        target_pin = pin or self.pin
        if not target_pin and not self.token:
            raise ValueError("Se requiere un PIN para emparejarse.")

        credenciales = {"pin": target_pin} if target_pin else {"token": self.token}
        req = Message.command(
            Action.PAIR_REQUEST,
            {**credenciales, "deviceType": self.device_type, "clientName": self.client_name},
            source=Source.CLIENT
        )
        assert self._ws is not None
        await self._ws.send(req.to_json())

        while True:
            resp_raw = await asyncio.wait_for(self._ws.recv(), timeout=self.timeout)
            resp = Message.from_json(resp_raw)

            if resp.action == Action.PAIRING_SUCCESS.value:
                self.is_paired = True
                self.token = resp.payload.get("token") or self.token
                return True
            elif resp.type == MessageType.ERROR:
                raise RuntimeError(f"Error de emparejamiento ({resp.payload.get('code')}): {resp.payload.get('reason')}")
            elif resp.action == Action.STATE_SYNC.value:
                self.latest_state = StateSyncPayload(**resp.payload)

    async def get_state(self) -> StateSyncPayload:
        """Obtiene el estado actual de la presentación."""
        if not self._ws:
            raise RuntimeError("Cliente no conectado.")

        if self.latest_state is not None:
            return self.latest_state

        await self._ws.send(Message.command(Action.GET_STATE).to_json())
        raw = await asyncio.wait_for(self._ws.recv(), timeout=self.timeout)
        msg = Message.from_json(raw)
        self.latest_state = StateSyncPayload(**msg.payload)
        return self.latest_state

    async def send_command(self, action: Action | str, payload: Optional[Dict[str, Any]] = None) -> Message:
        """Despacha un comando al daemon y aguarda la respuesta ACK o ERROR."""
        if not self._ws:
            raise RuntimeError("Cliente no conectado.")

        cmd = Message.command(action, payload or {}, source=Source.CLIENT)
        await self._ws.send(cmd.to_json())

        while True:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=self.timeout)
            msg = Message.from_json(raw)
            if msg.type in (MessageType.ACK, MessageType.ERROR):
                return msg
            elif msg.action == Action.STATE_SYNC.value:
                self.latest_state = StateSyncPayload(**msg.payload)

    async def listen_events(self) -> AsyncGenerator[Message, None]:
        """Generador asíncrono para monitoreo continuo de eventos."""
        if not self._ws:
            raise RuntimeError("Cliente no conectado.")

        async for raw in self._ws:
            try:
                yield Message.from_json(raw)
            except Exception:
                pass
