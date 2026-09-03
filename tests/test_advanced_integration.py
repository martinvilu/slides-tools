import asyncio
import pytest
from websockets.asyncio.client import connect

from slide_tools.client import SlideClient
from slide_tools.daemon import SlideDaemon
from slide_tools.protocol import (
    Action,
    ErrorCode,
    Message,
    MessageType,
    Source,
    SpeakerNotesData,
    StateSyncPayload,
    TimerData,
)


@pytest.fixture
async def running_server():
    daemon = SlideDaemon(host="127.0.0.1", port=0, pin="9999", require_pin=True, command_timeout=1.0)
    await daemon.start()
    port = daemon._server.sockets[0].getsockname()[1]
    uri = f"ws://127.0.0.1:{port}"
    yield daemon, uri
    await daemon.stop()


@pytest.mark.asyncio
async def test_navigation_and_visual_toggles(running_server):
    daemon, uri = running_server

    # Conectar extensión simulada
    async with connect(uri, proxy=None) as ext:
        await ext.recv()  # saludo
        st = StateSyncPayload(
            presentationTitle="Test Deck",
            isPresenting=True,
            currentSlide=5,
            totalSlides=30,
            speakerNotes=SpeakerNotesData(hasNotes=True, currentSlideNotes="Notas slide 5")
        )
        await ext.send(Message.state_sync(st, source=Source.EXTENSION).to_json())
        await asyncio.sleep(0.05)

        # Worker en la extensión para responder a los comandos
        async def ext_worker():
            while True:
                raw = await ext.recv()
                msg = Message.from_json(raw)
                if msg.type == MessageType.COMMAND:
                    req_id = msg.payload.get("requestId")
                    ack = Message.ack(msg.action, status="ok", extra={"requestId": req_id})
                    await ext.send(ack.to_json())

        worker_task = asyncio.create_task(ext_worker())

        try:
            async with SlideClient(uri=uri, pin="9999") as client:
                await client.pair()

                for act in (Action.PREV_SLIDE, Action.FIRST_SLIDE, Action.LAST_SLIDE,
                            Action.TOGGLE_BLACKOUT, Action.TOGGLE_WHITEOUT, Action.TOGGLE_LASER):
                    resp = await client.send_command(act)
                    assert resp.type == MessageType.ACK
                    assert resp.payload.get("status") == "ok"

                resp_goto = await client.send_command(Action.GO_TO_SLIDE, {"slideNumber": 12})
                assert resp_goto.type == MessageType.ACK
        finally:
            worker_task.cancel()


@pytest.mark.asyncio
async def test_client_disconnect_counter(running_server):
    daemon, uri = running_server

    async with SlideClient(uri=uri, pin="9999", client_name="C1") as c1:
        await c1.pair()
        assert daemon.paired_clients_count == 1

        async with SlideClient(uri=uri, pin="9999", client_name="C2") as c2:
            await c2.pair()
            assert daemon.paired_clients_count == 2

        # c2 se desconecta al salir de async with
        await asyncio.sleep(0.05)
        assert daemon.paired_clients_count == 1


@pytest.mark.asyncio
async def test_malformed_json(running_server):
    daemon, uri = running_server

    async with connect(uri, proxy=None) as client:
        await client.recv()  # saludo
        await client.send("{ este json es invalido")
        resp = Message.from_json(await asyncio.wait_for(client.recv(), timeout=2.0))
        assert resp.type == MessageType.ERROR
        assert resp.payload.get("code") == ErrorCode.ERR_MALFORMED_MESSAGE.value


@pytest.mark.asyncio
async def test_no_extension_connected_error(running_server):
    daemon, uri = running_server

    async with SlideClient(uri=uri, pin="9999") as client:
        await client.pair()
        # Intentar enviar NEXT_SLIDE sin extensión activa
        resp = await client.send_command(Action.NEXT_SLIDE)
        assert resp.type == MessageType.ERROR
        assert resp.payload.get("code") == ErrorCode.ERR_NOT_PRESENTING.value
