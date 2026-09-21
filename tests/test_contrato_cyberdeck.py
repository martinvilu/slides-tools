"""Contrato de slide-tools con su consumidor declarado (cyberdeck) — SLIDE-D0902.

cyberdeck es solo especificación (`cyberdeck/android-spec.md`): no hay cliente que
consuma este daemon. Estos tests fijan lo que la spec asume y que SÍ existe aquí,
para que un cambio de puerto, de servicio mDNS o del URI de emparejamiento no
rompa en silencio a un futuro cliente.
"""

import re

from typer.testing import CliRunner

from slide_tools.cli import app
from slide_tools.daemon import SlideDaemon
from slide_tools.discovery import build_pairing_uri
import inspect

runner = CliRunner()


def test_puerto_por_defecto_coincide_con_la_spec():
    firma = inspect.signature(SlideDaemon.__init__)
    assert firma.parameters["port"].default == 8766


def test_servicio_mdns_publicado():
    fuente = inspect.getsource(SlideDaemon)
    assert "_slide-bridge._tcp.local." in fuente


def test_uri_de_emparejamiento_v13():
    uri = build_pairing_uri("slides", "192.168.1.105", 8766, "4821", name="Workstation")
    assert uri == "bridge://pair?v=1.3&host=192.168.1.105&port=8766&service=slides&pin=4821&name=Workstation"
    assert re.fullmatch(r"bridge://pair\?v=1\.3(&[a-z]+=[^&]+)+", uri)
