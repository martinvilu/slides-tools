"""Daemon concentrador WebSocket para control de Google Slides con pairing y broadcast multicliente."""

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, Optional, Set
import websockets
from websockets.asyncio.server import Server, serve

from slide_tools.protocol import (
    Action,
    ErrorCode,
    Message,
    MessageType,
    PairRequestPayload,
    Source,
    SpeakerNotesData,
    StateSyncPayload,
    TimerData,
)

logger = logging.getLogger("slide_tools.daemon")


class ClientSession:
    """Información de sesión de un cliente WebSocket conectado."""

    def __init__(self, ws: Any, client_id: str, remote_ip: str = "127.0.0.1", is_paired: bool = False):
        self.ws = ws
        self.client_id = client_id
        self.remote_ip = remote_ip
        self.device_type: str = "unknown"
        self.client_name: str = "Cliente"
        self.is_paired: bool = is_paired


class SlideDaemon:
    """Servidor concentrador de control remoto para Google Slides."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8766,
        pin: Optional[str] = None,
        require_pin: bool = True,
        command_timeout: float = 2.5,
    ):
        self.host = host
        self.port = port
        self.pin = pin or f"{random.randint(1000, 9999)}"
        self.require_pin = require_pin
        self.command_timeout = command_timeout

        self._server: Optional[Server] = None
        self._extension_ws: Optional[Any] = None
        self._clients: Dict[Any, ClientSession] = {}
        self._pending_commands: Dict[str, asyncio.Future] = {}
        self._cmd_counter: int = 0

        # Estado canónico en memoria
        self.state = StateSyncPayload(
            presentationTitle="Sin presentación activa",
            isPresenting=False,
            presentationMode="standard",
            currentSlide=1,
            totalSlides=1,
            timer=TimerData(),
            speakerNotes=SpeakerNotesData(),
            connectedClients=0,
            pin=self.pin,
        )

        # Temporizador emulado (para fallback cuando no hay vista de orador)
        self._fallback_timer_running = False
        self._fallback_timer_start_time = 0.0
        self._fallback_timer_paused_elapsed = 0
        self._fallback_timer_task: Optional[asyncio.Task] = None

    @property
    def paired_clients_count(self) -> int:
        return sum(1 for c in self._clients.values() if c.is_paired and c.device_type != "extension")

    async def start(self) -> None:
        """Inicia el servidor WebSocket."""
        logger.info(f"Iniciando SlideDaemon en ws://{self.host}:{self.port} (PIN: {self.pin})")
        self._server = await serve(self._handle_connection, self.host, self.port)
        self._fallback_timer_task = asyncio.create_task(self._fallback_timer_loop())

    async def stop(self) -> None:
        """Detiene el servidor y limpia conexiones."""
        logger.info("Deteniendo SlideDaemon...")
        if self._fallback_timer_task:
            self._fallback_timer_task.cancel()
            try:
                await self._fallback_timer_task
            except asyncio.CancelledError:
                pass
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._clients.clear()
        self._extension_ws = None

    async def _handle_connection(self, websocket: Any) -> None:
        """Gestiona el ciclo de vida de una conexión entrante."""
        remote_ip = "127.0.0.1"
        try:
            remote_ip = websocket.remote_address[0]
        except Exception:
            pass

        client_id = f"c_{random.randint(10000, 99999)}"
        is_auto_paired = (remote_ip in ("127.0.0.1", "::1", "localhost") and not self.require_pin)
        session = ClientSession(websocket, client_id, remote_ip, is_paired=is_auto_paired)
        self._clients[websocket] = session

        logger.info(f"Nueva conexión desde {remote_ip} [id={client_id}]")
        await self._send_state(websocket)

        try:
            async for raw_message in websocket:
                try:
                    msg = Message.from_json(raw_message)
                except Exception as e:
                    logger.warning(f"Mensaje malformado: {e}")
                    err = Message.error(f"Mensaje malformado: {e}", ErrorCode.ERR_MALFORMED_MESSAGE)
                    await websocket.send(err.to_json())
                    continue

                await self._process_message(websocket, session, msg)

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if self._extension_ws == websocket:
                self._extension_ws = None
                self.state.isPresenting = False
                logger.info("Extensión WebExtensions desconectada")
                await self._broadcast_state()

            if websocket in self._clients:
                del self._clients[websocket]
                self.state.connectedClients = self.paired_clients_count
                logger.info(f"Cliente desconectado [id={client_id}]")
                await self._broadcast_state()

    async def _process_message(self, websocket: Any, session: ClientSession, msg: Message) -> None:
        """Enruta y procesa mensajes según procedencia y estado de pairing."""

        # 1. Mensajes emitidos por la extensión WebExtensions
        if msg.source == Source.EXTENSION:
            if self._extension_ws != websocket:
                self._extension_ws = websocket
                session.device_type = "extension"
                session.is_paired = True
                logger.info("Extensión de Google Slides registrada exitosamente")

            if msg.action == Action.STATE_SYNC.value:
                incoming_payload = dict(msg.payload)
                incoming_payload["pin"] = self.pin
                incoming_payload["connectedClients"] = self.paired_clients_count
                self.state = StateSyncPayload(**incoming_payload)
                # Difundir a los clientes, sin rebotarle su propio sync a la extensión
                await self._broadcast_state(exclude_ws=websocket)
                return

            if msg.type in (MessageType.ACK, MessageType.ERROR):
                req_id = msg.payload.get("requestId")
                if req_id and req_id in self._pending_commands:
                    fut = self._pending_commands.pop(req_id)
                    if not fut.done():
                        fut.set_result(msg)
                return

        # 2. Solicitudes de emparejamiento (PAIR_REQUEST)
        if msg.action == Action.PAIR_REQUEST.value:
            req_pin = str(msg.payload.get("pin", "")).strip()
            if not self.require_pin or req_pin == self.pin:
                session.is_paired = True
                session.device_type = str(msg.payload.get("deviceType", "android"))
                session.client_name = str(msg.payload.get("clientName", "Dispositivo"))
                self.state.connectedClients = self.paired_clients_count
                logger.info(f"Cliente emparejado: {session.client_name} ({session.device_type})")

                ack = Message(
                    source=Source.DAEMON,
                    type=MessageType.EVENT,
                    action=Action.PAIRING_SUCCESS.value,
                    payload={"clientId": session.client_id, "deviceType": session.device_type, "status": "ok"}
                )
                await websocket.send(ack.to_json())
                await self._broadcast_state()
            else:
                err = Message.error("PIN de emparejamiento incorrecto.", ErrorCode.ERR_INVALID_PIN)
                await websocket.send(err.to_json())
            return

        # 3. Consulta de estado (GET_STATE)
        if msg.action == Action.GET_STATE.value:
            await self._send_state(websocket)
            return

        # 4. Comandos de control
        if msg.type == MessageType.COMMAND:
            if not session.is_paired and self.require_pin:
                err = Message.error("Emparejamiento requerido mediante PIN.", ErrorCode.ERR_PAIRING_REQUIRED)
                await websocket.send(err.to_json())
                return

            # Manejo local de temporizador en modo fallback
            if msg.action == Action.TIMER_RESET.value and self.state.presentationMode != "presenter_view":
                self._reset_fallback_timer()
                await self._broadcast_state()
                await websocket.send(Message.ack(msg.action, status="ok").to_json())
                return

            if msg.action == Action.TIMER_TOGGLE_PAUSE.value and self.state.presentationMode != "presenter_view":
                self._toggle_pause_fallback_timer()
                await self._broadcast_state()
                await websocket.send(Message.ack(msg.action, status="ok").to_json())
                return

            if not self._extension_ws:
                err = Message.error(
                    "No hay ninguna presentación de Google Slides conectada.",
                    ErrorCode.ERR_NOT_PRESENTING
                )
                await websocket.send(err.to_json())
                return

            # Enrutar a la extensión
            self._cmd_counter += 1
            req_id = f"cmd_{self._cmd_counter}"
            payload = dict(msg.payload)
            payload["requestId"] = req_id

            fwd_msg = Message.command(msg.action, payload, source=Source.DAEMON)
            loop = asyncio.get_running_loop()
            fut: asyncio.Future = loop.create_future()
            self._pending_commands[req_id] = fut

            try:
                await self._extension_ws.send(fwd_msg.to_json())
                resp = await asyncio.wait_for(fut, timeout=self.command_timeout)
                resp_to_client = Message(
                    version=resp.version,
                    source=Source.DAEMON,
                    type=resp.type,
                    action=resp.action,
                    payload=resp.payload
                )
                await websocket.send(resp_to_client.to_json())
            except asyncio.TimeoutError:
                self._pending_commands.pop(req_id, None)
                ack = Message.ack(msg.action, status="ok", details="dispatched_timeout_ack")
                await websocket.send(ack.to_json())
            except Exception as e:
                self._pending_commands.pop(req_id, None)
                err = Message.error(f"Error despachando comando a la extensión: {e}", ErrorCode.ERR_EXTENSION_DISCONNECTED)
                await websocket.send(err.to_json())

    async def _send_state(self, websocket: Any) -> None:
        msg = Message.state_sync(self.state, source=Source.DAEMON)
        try:
            await websocket.send(msg.to_json())
        except Exception:
            pass

    async def _broadcast_state(self, exclude_ws: Optional[Any] = None) -> None:
        """Difunde el estado consolidado a todos los clientes emparejados y a la extensión."""
        if not self._clients:
            return
        msg = Message.state_sync(self.state, source=Source.DAEMON)
        raw = msg.to_json()
        dead_clients = set()

        for ws, sess in list(self._clients.items()):
            if ws == exclude_ws:
                continue
            if sess.is_paired or ws == self._extension_ws:
                try:
                    await ws.send(raw)
                except Exception:
                    dead_clients.add(ws)

        for ws in dead_clients:
            self._clients.pop(ws, None)

    # -------------------------------------------------------------------------
    # Temporizador de Respaldo (Fallback)
    # -------------------------------------------------------------------------

    def _reset_fallback_timer(self) -> None:
        self._fallback_timer_start_time = time.time()
        self._fallback_timer_paused_elapsed = 0
        self.state.timer.elapsedSeconds = 0
        self.state.timer.formattedTime = "00:00"
        self.state.timer.isPaused = False
        self._fallback_timer_running = True

    def _toggle_pause_fallback_timer(self) -> None:
        if self._fallback_timer_running:
            self._fallback_timer_paused_elapsed += int(time.time() - self._fallback_timer_start_time)
            self._fallback_timer_running = False
            self.state.timer.isPaused = True
        else:
            self._fallback_timer_start_time = time.time()
            self._fallback_timer_running = True
            self.state.timer.isPaused = False

    async def _fallback_timer_loop(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            if self._fallback_timer_running and self.state.presentationMode != "presenter_view":
                elapsed = self._fallback_timer_paused_elapsed + int(time.time() - self._fallback_timer_start_time)
                mins = elapsed // 60
                secs = elapsed % 60
                self.state.timer.elapsedSeconds = elapsed
                self.state.timer.formattedTime = f"{mins:02d}:{secs:02d}"
                await self._broadcast_state()
