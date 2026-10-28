"""Atajos de teclado globales y estado para la bandeja (Ola 24)."""

from typer.testing import CliRunner

from slide_tools.cli import app, atajos_de_slides, evaluar_estado_slides


def test_atajos_con_ruta_absoluta_y_notificacion():
    lista = atajos_de_slides("ws://127.0.0.1:9000")
    assert [a.combinacion for a in lista] == ["<Control><Alt>Page_Down", "<Control><Alt>Page_Up", "<Control><Alt>b",
                                               "<Control><Alt>p", "<Control><Alt>r"]
    assert all(a.clave.startswith("p1-slides-") and a.comando.endswith("--uri ws://127.0.0.1:9000 --notificar")
               for a in lista)


def test_atajos_fuera_de_gnome(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    res = CliRunner().invoke(app, ["atajos", "--instalar"])
    assert res.exit_code == 0 and "sólo funciona en GNOME" in res.output


def test_los_comandos_de_los_atajos_aceptan_notificar():
    for sub in ("next", "prev", "blackout", "timer-pause", "timer-reset"):
        assert "--notificar" in CliRunner().invoke(app, [sub, "--help"]).output


def test_estado_para_la_bandeja():
    assert evaluar_estado_slides({"isPresenting": True, "presentationTitle": "Punteros", "currentSlide": 3,
                                  "totalSlides": 20}) == (True, "Presentando «Punteros» (3/20)")
    assert evaluar_estado_slides({}) == (False, "Daemon activo, sin presentación en el navegador")
