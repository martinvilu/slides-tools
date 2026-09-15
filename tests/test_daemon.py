import asyncio
import pytest
from websockets.asyncio.client import connect

from slide_tools.daemon import SlideDaemon
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


@pytest.fixture
async def daemon_fixture():
    daemon = SlideDaemon(host="127.0.0.1", port=0, pin="4821", require_pin=True, command_timeout=1.0)
    await daemon.start()
    port = daemon._server.sockets[0].getsockname()[1]
    uri = f"ws://127.0.0.1:{port}"
    yield daemon, uri
    await daemon.stop()


@pytest.mark.asyncio
async def test_pairing_required_and_invalid_pin(daemon_fixture):
    daemon, uri = daemon_fixture

    async with connect(uri, proxy=None) as client:
        # 1. Saludo inicial con PIN
        init_raw = await asyncio.wait_for(client.recv(), timeout=2.0)
        init_msg = Message.from_json(init_raw)
        assert init_msg.action == Action.STATE_SYNC.value
        assert init_msg.payload["pin"] == "4821"

        # 2. Intentar comandar sin emparejarse
        await client.send(Message.command(Action.NEXT_SLIDE, source=Source.ANDROID).to_json())
        resp_err = Message.from_json(await asyncio.wait_for(client.recv(), timeout=2.0))
        assert resp_err.type == MessageType.ERROR
        assert resp_err.payload["code"] == ErrorCode.ERR_PAIRING_REQUIRED.value

        # 3. Intentar emparejarse con PIN erróneo
        await client.send(Message.command(Action.PAIR_REQUEST, {"pin": "0000"}).to_json())
        resp_pin_err = Message.from_json(await asyncio.wait_for(client.recv(), timeout=2.0))
        assert resp_pin_err.type == MessageType.ERROR
        assert resp_pin_err.payload["code"] == ErrorCode.ERR_INVALID_PIN.value


@pytest.mark.asyncio
async def test_successful_pairing_and_multiclient_broadcast(daemon_fixture):
    daemon, uri = daemon_fixture

    # Conectar extensión
    async with connect(uri, proxy=None) as ext:
        await ext.recv()  # saludo
        # Extensión envía estado de presentación
        ext_state = StateSyncPayload(
            presentationTitle="Arquitectura 2026",
            isPresenting=True,
            currentSlide=1,
            totalSlides=10,
            speakerNotes=SpeakerNotesData(hasNotes=True, currentSlideNotes="Slide 1 notes")
        )
        await ext.send(Message.state_sync(ext_state, source=Source.EXTENSION).to_json())
        await asyncio.sleep(0.05)

        # Conectar Cliente 1 (Android)
        async with connect(uri, proxy=None) as android:
            await android.recv()
            # Emparejamiento
            await android.send(Message.command(Action.PAIR_REQUEST, {"pin": "4821", "deviceType": "android"}).to_json())
            p1_ack = Message.from_json(await asyncio.wait_for(android.recv(), timeout=2.0))
            assert p1_ack.action == Action.PAIRING_SUCCESS.value
            await android.recv()  # broadcast de nuevo estado

            # Extensión recibe actualización de clientes conectados (1 cliente)
            ext_sync1 = Message.from_json(await asyncio.wait_for(ext.recv(), timeout=2.0))
            assert ext_sync1.payload["connectedClients"] == 1

            # Conectar Cliente 2 (Hardware Wi-Fi)
            async with connect(uri, proxy=None) as hw:
                await hw.recv()
                await hw.send(Message.command(Action.PAIR_REQUEST, {"pin": "4821", "deviceType": "hardware"}).to_json())
                p2_ack = Message.from_json(await asyncio.wait_for(hw.recv(), timeout=2.0))
                assert p2_ack.action == Action.PAIRING_SUCCESS.value
                await hw.recv()  # broadcast para hw
                await android.recv()  # android recibe broadcast de 2 clientes conectados

                # Extensión recibe actualización de clientes conectados (2 clientes)
                ext_sync2 = Message.from_json(await asyncio.wait_for(ext.recv(), timeout=2.0))
                assert ext_sync2.payload["connectedClients"] == 2

                # Hardware envía NEXT_SLIDE
                await hw.send(Message.command(Action.NEXT_SLIDE, source=Source.HARDWARE).to_json())

                # Extensión recibe comando
                ext_cmd = Message.from_json(await asyncio.wait_for(ext.recv(), timeout=2.0))
                assert ext_cmd.action == Action.NEXT_SLIDE.value
                req_id = ext_cmd.payload["requestId"]

                # Extensión responde con ACK y nuevo estado (slide 2)
                ack_msg = Message.ack("NEXT_SLIDE", status="ok", extra={"requestId": req_id})
                await ext.send(ack_msg.to_json())

                # Hardware que envió el comando recibe ACK
                hw_ack = Message.from_json(await asyncio.wait_for(hw.recv(), timeout=2.0))
                assert hw_ack.type == MessageType.ACK

                # Extensión emite nuevo STATE_SYNC
                ext_state.currentSlide = 2
                ext_state.speakerNotes.currentSlideNotes = "Slide 2 notes"
                await ext.send(Message.state_sync(ext_state, source=Source.EXTENSION).to_json())

                # Ambos clientes (Android y HW) reciben el nuevo estado sincronizado
                android_sync = Message.from_json(await asyncio.wait_for(android.recv(), timeout=2.0))
                assert android_sync.payload["currentSlide"] == 2
                assert android_sync.payload["speakerNotes"]["currentSlideNotes"] == "Slide 2 notes"

                hw_sync = Message.from_json(await asyncio.wait_for(hw.recv(), timeout=2.0))
                assert hw_sync.payload["currentSlide"] == 2


@pytest.mark.asyncio
async def test_fallback_timer_control(daemon_fixture):
    daemon, uri = daemon_fixture

    async with connect(uri, proxy=None) as client:
        await client.recv()
        await client.send(Message.command(Action.PAIR_REQUEST, {"pin": "4821"}).to_json())
        await client.recv()  # PAIRING_SUCCESS
        await client.recv()  # broadcast de estado

        # Enviar TIMER_RESET
        await client.send(Message.command(Action.TIMER_RESET).to_json())
        msg1 = Message.from_json(await asyncio.wait_for(client.recv(), timeout=2.0))
        assert msg1.action in (Action.COMMAND_ACK.value, Action.STATE_SYNC.value)


@pytest.mark.asyncio
async def test_daemon_pin_rate_limiting(daemon_fixture):
    daemon, uri = daemon_fixture

    async with connect(uri, proxy=None) as client:
        await client.recv()  # drain initial state
        # Send 5 incorrect PIN attempts
        for i in range(5):
            bad_req = Message.command(Action.PAIR_REQUEST, {"pin": f"000{i}"})
            await client.send(bad_req.to_json())
            resp = Message.from_json(await asyncio.wait_for(client.recv(), timeout=3.0))
            assert resp.type == MessageType.ERROR
            assert resp.payload["code"] == ErrorCode.ERR_INVALID_PIN.value

        # 6th attempt: should be blocked by rate limit
        bad_req = Message.command(Action.PAIR_REQUEST, {"pin": "4821"})
        await client.send(bad_req.to_json())
        blocked_resp = Message.from_json(await asyncio.wait_for(client.recv(), timeout=2.0))
        assert blocked_resp.type == MessageType.ERROR
        assert "Demasiados intentos" in blocked_resp.payload["reason"]
