"""Emparejamiento seguro: PIN, tokens de reconexión, origen web y confianza local (Ola 24)."""

import asyncio

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from slide_tools.client import SlideClient
from slide_tools.daemon import SlideDaemon
from slide_tools.protocol import Action, ErrorCode, Message, Source, StateSyncPayload


async def _daemon(**kw):
    daemon = SlideDaemon(host="127.0.0.1", port=0, pin="482913", require_pin=True, enable_mdns=False,
                         command_timeout=0.5, **kw)
    await daemon.start()
    return daemon, f"ws://127.0.0.1:{daemon._server.sockets[0].getsockname()[1]}"


async def _recibir(ws):
    return Message.from_json(await asyncio.wait_for(ws.recv(), timeout=3))


@pytest.mark.asyncio
async def test_decir_que_es_la_extension_no_empareja():
    """Antes bastaba con `source: extension` para quedar emparejado y manejar la presentación."""
    daemon, uri = await _daemon(confiar_en_local=False)
    try:
        async with connect(uri, proxy=None) as intruso:
            assert (await _recibir(intruso)).payload["pin"] == ""
            await intruso.send(Message.state_sync(StateSyncPayload(isPresenting=True), source=Source.EXTENSION).to_json())
            assert (await _recibir(intruso)).payload["code"] == ErrorCode.ERR_PAIRING_REQUIRED.value
            assert daemon._extension_ws is None and daemon.state.isPresenting is False
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_una_pagina_web_no_puede_conectarse():
    daemon, uri = await _daemon()
    try:
        with pytest.raises(InvalidStatus) as exc:
            async with connect(uri, proxy=None, origin="https://sitio-malicioso.example"):
                pass
        assert exc.value.response.status_code == 403
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_la_extension_local_no_necesita_pin():
    daemon, uri = await _daemon()
    try:
        async with connect(uri, proxy=None, origin="moz-extension://slide-bridge") as ext:
            assert (await _recibir(ext)).payload["pin"] == "482913"
            await ext.send(Message.state_sync(StateSyncPayload(isPresenting=True), source=Source.EXTENSION).to_json())
            await asyncio.sleep(0.1)
            assert daemon._extension_ws is not None and daemon.state.isPresenting is True
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_reconexion_con_token_sin_pin():
    daemon, uri = await _daemon(confiar_en_local=False)
    try:
        async with SlideClient(uri=uri, pin="482913") as cliente:
            await cliente.pair()
            token = cliente.token
        assert token
        otro = SlideClient(uri=uri)
        otro.token = token
        async with otro:
            assert await otro.pair() is True
        daemon._tokens.revocar_todos()
        vencido = SlideClient(uri=uri)
        vencido.token = token
        async with vencido:
            with pytest.raises(RuntimeError, match="ERR_INVALID_PIN"):
                await vencido.pair()
    finally:
        await daemon.stop()
