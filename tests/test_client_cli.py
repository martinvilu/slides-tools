import asyncio
import threading
import time
import pytest
from typer.testing import CliRunner

from slide_tools.cli import app
from slide_tools.client import SlideClient
from slide_tools.daemon import SlideDaemon
from slide_tools.protocol import Action, Message, Source, StateSyncPayload
from websockets.asyncio.client import connect

runner = CliRunner()


@pytest.fixture
def thread_daemon():
    loop = asyncio.new_event_loop()
    daemon = SlideDaemon(host="127.0.0.1", port=0, pin="1234", require_pin=True)

    def _run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(daemon.start())
        loop.run_forever()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    time.sleep(0.1)

    port = daemon._server.sockets[0].getsockname()[1]
    uri = f"ws://127.0.0.1:{port}"

    yield daemon, uri

    # Detener daemon limpiamente en su loop
    future = asyncio.run_coroutine_threadsafe(daemon.stop(), loop)
    future.result(timeout=2.0)
    loop.call_soon_threadsafe(loop.stop)
    t.join(timeout=1.0)


def test_cli_help():
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "Sistema de control remoto para Google Slides" in res.stdout


def test_cli_status(thread_daemon):
    daemon, uri = thread_daemon
    res = runner.invoke(app, ["status", "--uri", uri])
    assert res.exit_code == 0
    assert "Estado de Google Slides" in res.stdout
    assert "PIN de Sesión" in res.stdout
    assert "1234" in res.stdout


def test_cli_command_without_pairing_rejected(thread_daemon):
    daemon, uri = thread_daemon
    res = runner.invoke(app, ["next", "--uri", uri])
    assert res.exit_code == 0
    assert "ERR_PAIRING_REQUIRED" in res.stdout


def test_cli_command_with_correct_pin(thread_daemon):
    daemon, uri = thread_daemon
    res = runner.invoke(app, ["timer-reset", "--uri", uri, "--pin", "1234"])
    assert res.exit_code == 0
    assert "Comando ejecutado" in res.stdout
