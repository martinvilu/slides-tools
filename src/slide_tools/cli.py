"""Interfaz de línea de comandos (CLI) para slide-tools."""

import asyncio
import logging
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

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

app = typer.Typer(help="Sistema de control remoto para Google Slides.", no_args_is_help=True)
console = Console()


@app.command()
def daemon(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Dirección IP de escucha"),
    port: int = typer.Option(8766, "--port", "-p", help="Puerto TCP WebSocket"),
    pin: Optional[str] = typer.Option(None, "--pin", help="PIN de 4 dígitos fijo (si se omite, se genera aleatorio)"),
    no_pin: bool = typer.Option(False, "--no-pin", help="Desactivar requerimiento de PIN (modo permisivo)"),
    no_mdns: bool = typer.Option(False, "--no-mdns", help="Desactivar publicación mDNS/Zeroconf"),
    no_qr: bool = typer.Option(False, "--no-qr", help="Ocultar código QR en la consola"),
    timeout: float = typer.Option(2.5, "--timeout", "-t", help="Timeout de respuesta de extensión"),
):
    """Inicia el daemon concentrador WebSocket en primer plano."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    server = SlideDaemon(
        host=host,
        port=port,
        pin=pin,
        require_pin=not no_pin,
        command_timeout=timeout,
        enable_mdns=not no_mdns,
    )

    mdns_info = "[bold green]Activo[/bold green] (_slide-bridge._tcp.local.)" if not no_mdns else "[dim]Desactivado[/dim]"
    console.print(Panel.fit(
        f"[bold cyan]Slide Daemon Concentrador v1.2[/bold cyan]\n"
        f"Escuchando en: [bold green]ws://{host}:{port}[/bold green]\n"
        f"PIN de Emparejamiento: [bold yellow]{server.pin}[/bold yellow] {'(Opcional)' if no_pin else '(Requerido)'}\n"
        f"Descubrimiento mDNS: {mdns_info}\n"
        f"Conexión LAN: [dim]ws://{server.lan_ip}:{port}[/dim]\n"
        f"URI Emparejamiento: [cyan]{server.pairing_uri}[/cyan]",
        border_style="cyan"
    ))

    if not no_qr:
        console.print("[dim]Escaneá este código QR desde la app Android para conectar directo:[/dim]")
        console.print(server.qr_ascii)
        console.print("")

    async def _run():
        await server.start()
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            await server.stop()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Daemon detenido por el usuario.[/yellow]")


def _send_cmd_helper(
    action: Action,
    uri: str = "ws://127.0.0.1:8766",
    pin: Optional[str] = None,
    payload: Optional[dict] = None
) -> None:
    async def _run():
        try:
            async with SlideClient(uri=uri, pin=pin) as client:
                if pin:
                    await client.pair(pin)
                resp = await client.send_command(action, payload or {})
                if resp.type == MessageType.ACK:
                    console.print(f"[bold green]✓ Comando ejecutado:[/bold green] {action.value}")
                elif resp.type == MessageType.ERROR:
                    console.print(f"[bold red]✗ Error ({resp.payload.get('code')}):[/bold red] {resp.payload.get('reason')}")
                else:
                    console.print(f"[cyan]Respuesta:[/cyan] {resp.action} {resp.payload}")
        except Exception as e:
            console.print(f"[bold red]Error comunicando con daemon en {uri}:[/bold red] {e}")

    asyncio.run(_run())


@app.command()
def status(
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u", help="URI del daemon"),
):
    """Muestra el estado consolidado de la presentación activa."""
    async def _run():
        try:
            async with SlideClient(uri=uri) as client:
                st = await client.get_state()
                table = Table(title="Estado de Google Slides", border_style="cyan")
                table.add_column("Parámetro", style="bold white")
                table.add_column("Valor", style="bold")

                table.add_row("Título", st.presentationTitle or "[dim]Sin título[/dim]")
                table.add_row("Presentando", "[green]Sí[/green]" if st.isPresenting else "[red]No[/red]")
                table.add_row("Modo", f"[cyan]{st.presentationMode}[/cyan]")
                table.add_row("Diapositiva", f"{st.currentSlide} / {st.totalSlides}")
                table.add_row("Pantalla Negra (B)", "[yellow]Activa[/yellow]" if st.isBlackout else "[dim]Inactiva[/dim]")
                table.add_row("Pantalla Blanca (W)", "[yellow]Activa[/yellow]" if st.isWhiteout else "[dim]Inactiva[/dim]")
                table.add_row("Puntero Láser (L)", "[red]Activo[/red]" if st.isLaserActive else "[dim]Inactivo[/dim]")
                table.add_row("Temporizador", f"{st.timer.formattedTime} {'[yellow](Pausa)[/yellow]' if st.timer.isPaused else ''}")
                table.add_row("Clientes Conectados", str(st.connectedClients))
                table.add_row("PIN de Sesión", f"[bold yellow]{st.pin}[/bold yellow]")

                notes_preview = st.speakerNotes.currentSlideNotes
                if len(notes_preview) > 60:
                    notes_preview = notes_preview[:57] + "..."
                table.add_row("Notas de Orador", notes_preview if st.speakerNotes.hasNotes else "[dim]Sin notas[/dim]")

                console.print(table)
        except Exception as e:
            console.print(f"[bold red]Error conectando con {uri}:[/bold red] {e}")

    asyncio.run(_run())


@app.command()
def next(
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
    pin: Optional[str] = typer.Option(None, "--pin", "-k"),
):
    """Avanza a la siguiente diapositiva o animación (NEXT_SLIDE)."""
    _send_cmd_helper(Action.NEXT_SLIDE, uri=uri, pin=pin)


@app.command()
def prev(
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
    pin: Optional[str] = typer.Option(None, "--pin", "-k"),
):
    """Retrocede a la diapositiva o animación anterior (PREV_SLIDE)."""
    _send_cmd_helper(Action.PREV_SLIDE, uri=uri, pin=pin)


@app.command()
def first(
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
    pin: Optional[str] = typer.Option(None, "--pin", "-k"),
):
    """Salta a la primera diapositiva (FIRST_SLIDE)."""
    _send_cmd_helper(Action.FIRST_SLIDE, uri=uri, pin=pin)


@app.command()
def last(
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
    pin: Optional[str] = typer.Option(None, "--pin", "-k"),
):
    """Salta a la última diapositiva (LAST_SLIDE)."""
    _send_cmd_helper(Action.LAST_SLIDE, uri=uri, pin=pin)


@app.command()
def goto(
    slide: int = typer.Argument(..., help="Número de diapositiva de destino"),
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
    pin: Optional[str] = typer.Option(None, "--pin", "-k"),
):
    """Salta directamente a una diapositiva específica (GO_TO_SLIDE)."""
    _send_cmd_helper(Action.GO_TO_SLIDE, uri=uri, pin=pin, payload={"slideNumber": slide})


@app.command()
def blackout(
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
    pin: Optional[str] = typer.Option(None, "--pin", "-k"),
):
    """Conmuta pantalla en negro (TOGGLE_BLACKOUT)."""
    _send_cmd_helper(Action.TOGGLE_BLACKOUT, uri=uri, pin=pin)


@app.command()
def whiteout(
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
    pin: Optional[str] = typer.Option(None, "--pin", "-k"),
):
    """Conmuta pantalla en blanco (TOGGLE_WHITEOUT)."""
    _send_cmd_helper(Action.TOGGLE_WHITEOUT, uri=uri, pin=pin)


@app.command()
def laser(
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
    pin: Optional[str] = typer.Option(None, "--pin", "-k"),
):
    """Conmuta puntero láser virtual (TOGGLE_LASER)."""
    _send_cmd_helper(Action.TOGGLE_LASER, uri=uri, pin=pin)


@app.command("timer-reset")
def timer_reset(
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
    pin: Optional[str] = typer.Option(None, "--pin", "-k"),
):
    """Reinicia el temporizador (TIMER_RESET)."""
    _send_cmd_helper(Action.TIMER_RESET, uri=uri, pin=pin)


@app.command("timer-pause")
def timer_pause(
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
    pin: Optional[str] = typer.Option(None, "--pin", "-k"),
):
    """Pausa o reanuda el temporizador (TIMER_TOGGLE_PAUSE)."""
    _send_cmd_helper(Action.TIMER_TOGGLE_PAUSE, uri=uri, pin=pin)


@app.command()
def monitor(
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
    pin: Optional[str] = typer.Option(None, "--pin", "-k"),
):
    """Monitorea en tiempo real cambios de diapositiva, notas y cronómetro."""
    async def _run():
        console.print(f"[cyan]Conectando a {uri} para monitoreo continuo... (Ctrl+C para salir)[/cyan]")
        try:
            async with SlideClient(uri=uri, pin=pin) as client:
                if pin:
                    await client.pair(pin)
                async for msg in client.listen_events():
                    if msg.action == Action.STATE_SYNC.value:
                        p = msg.payload
                        timer = p.get("timer", {})
                        notes = p.get("speakerNotes", {})
                        console.print(
                            f"[bold green][SLIDE {p.get('currentSlide')}/{p.get('totalSlides')}][/bold green] "
                            f"Timer: {timer.get('formattedTime')} | Mode: {p.get('presentationMode')} | "
                            f"Laser: {p.get('isLaserActive')} | Clients: {p.get('connectedClients')}"
                        )
                        if notes.get("hasNotes"):
                            console.print(f"  [dim]Notas:[/dim] {notes.get('currentSlideNotes')}")
                    else:
                        console.print(f"[dim]{msg.action}[/dim] {msg.payload}")
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoreo finalizado.[/yellow]")
        except Exception as e:
            console.print(f"[bold red]Error durante monitoreo:[/bold red] {e}")

    asyncio.run(_run())


@app.command("mock-slides")
def mock_slides(
    total_slides: int = typer.Option(10, "--slides", "-s", help="Cantidad de diapositivas simuladas"),
    uri: str = typer.Option("ws://127.0.0.1:8766", "--uri", "-u"),
):
    """Simula una sesión de Google Slides conectada al daemon para pruebas."""
    import websockets
    from websockets.asyncio.client import connect

    async def _run():
        console.print(f"[cyan]Iniciando presentación simulada con {total_slides} diapositivas hacia {uri}...[/cyan]")
        state = StateSyncPayload(
            presentationTitle="Presentación Simulada",
            isPresenting=True,
            presentationMode="presenter_view",
            currentSlide=1,
            totalSlides=total_slides,
            speakerNotes=SpeakerNotesData(hasNotes=True, currentSlideNotes="Nota de la diapositiva 1"),
            timer=TimerData(elapsedSeconds=0, formattedTime="00:00")
        )

        async with connect(uri, proxy=None) as ws:
            await ws.recv()  # saludo
            # Registrar como extensión
            await ws.send(Message.state_sync(state, source=Source.EXTENSION).to_json())
            console.print("[green]Presentación simulada conectada. Esperando comandos remotos...[/green]")

            async for raw in ws:
                msg = Message.from_json(raw)
                console.print(f"[dim]Presentación recibió:[/dim] {msg.action} {msg.payload}")

                if msg.type == MessageType.COMMAND:
                    req_id = msg.payload.get("requestId")
                    if msg.action == Action.NEXT_SLIDE.value:
                        if state.currentSlide < state.totalSlides:
                            state.currentSlide += 1
                            state.speakerNotes.currentSlideNotes = f"Nota de la diapositiva {state.currentSlide}"
                    elif msg.action == Action.PREV_SLIDE.value:
                        if state.currentSlide > 1:
                            state.currentSlide -= 1
                            state.speakerNotes.currentSlideNotes = f"Nota de la diapositiva {state.currentSlide}"
                    elif msg.action == Action.FIRST_SLIDE.value:
                        state.currentSlide = 1
                    elif msg.action == Action.LAST_SLIDE.value:
                        state.currentSlide = state.totalSlides
                    elif msg.action == Action.GO_TO_SLIDE.value:
                        target = int(msg.payload.get("slideNumber", 1))
                        if 1 <= target <= state.totalSlides:
                            state.currentSlide = target
                    elif msg.action == Action.TOGGLE_BLACKOUT.value:
                        state.isBlackout = not state.isBlackout
                    elif msg.action == Action.TOGGLE_WHITEOUT.value:
                        state.isWhiteout = not state.isWhiteout
                    elif msg.action == Action.TOGGLE_LASER.value:
                        state.isLaserActive = not state.isLaserActive

                    # Enviar ACK y STATE_SYNC
                    ack = Message.ack(msg.action, status="ok", extra={"requestId": req_id})
                    await ws.send(ack.to_json())
                    await ws.send(Message.state_sync(state, source=Source.EXTENSION).to_json())
                    console.print(f"[bold green]Diapositiva actual -> {state.currentSlide}/{state.totalSlides}[/bold green]")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Presentación simulada cerrada.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error en presentación simulada:[/bold red] {e}")


@app.command()
def pack(
    target: str = typer.Option("both", "--target", "-t", help="Navegador objetivo: chrome, firefox o both"),
    out_dir: str = typer.Option("dist", "--out-dir", "-o", help="Directorio de salida para los paquetes"),
):
    """Empaqueta la extensión WebExtensions para Chrome (.zip) y Firefox (.xpi)."""
    from pathlib import Path
    from slide_tools.packer import package_extension

    try:
        res = package_extension(target=target, output_dir=Path(out_dir))
        for tgt, p in res.items():
            console.print(f"[bold green]✓ Paquete generado ({tgt}):[/bold green] [cyan]{p}[/cyan]")
    except Exception as e:
        console.print(f"[bold red]Error al empaquetar:[/bold red] {e}")


@app.command()
def sign(
    api_key: Optional[str] = typer.Option(None, "--api-key", "-k", help="API Key (JWT issuer) de Mozilla AMO"),
    api_secret: Optional[str] = typer.Option(None, "--api-secret", "-s", help="API Secret de Mozilla AMO"),
    channel: str = typer.Option("unlisted", "--channel", "-c", help="Canal de distribución: unlisted o listed"),
    out_dir: str = typer.Option("dist", "--out-dir", "-o", help="Directorio destino para el .xpi firmado"),
    lint_only: bool = typer.Option(False, "--lint-only", help="Solo validar compatibilidad y manifiesto con web-ext lint"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Verificar manifiesto e imprimir el comando web-ext sign sin enviar"),
):
    """Valida y firma digitalmente el addon para Firefox utilizando Mozilla web-ext."""
    from pathlib import Path
    from slide_tools.signer import sign_firefox_addon

    try:
        res = sign_firefox_addon(
            output_dir=Path(out_dir),
            api_key=api_key,
            api_secret=api_secret,
            channel=channel,
            lint_only=lint_only,
            dry_run=dry_run
        )
        if dry_run:
            console.print("[bold yellow]Modo Dry-Run activo:[/bold yellow]")
            console.print(f"Comando planificado: [cyan]{res['command']}[/cyan]")
            console.print(f"Credenciales detectadas: {'[green]Sí[/green]' if res['credentials_present'] else '[red]No[/red]'}")
        elif lint_only:
            console.print("[bold green]✓ Validación web-ext lint superada con éxito.[/bold green]")
            if res.get("lint_output"):
                console.print(f"[dim]{res['lint_output']}[/dim]")
        else:
            console.print(f"[bold green]✓ Addon firmado exitosamente:[/bold green] [cyan]{res['signed_file']}[/cyan]")
    except Exception as e:
        console.print(f"[bold red]Error durante firma con web-ext:[/bold red] {e}")


@app.command()
def qr(
    port: int = typer.Option(8766, "--port", "-p", help="Puerto TCP WebSocket"),
    pin: str = typer.Option(..., "--pin", help="PIN de emparejamiento"),
    host: Optional[str] = typer.Option(None, "--host", "-h", help="IP anfitrión (si se omite, se detecta automáticamente)"),
):
    """Muestra el código QR para emparejamiento directo con la app Android."""
    from slide_tools.discovery import build_pairing_uri, generate_qr_ascii, get_local_ip
    lan_ip = host or get_local_ip()
    uri = build_pairing_uri("slides", lan_ip, port, pin)
    console.print(f"[bold cyan]URI de Emparejamiento Directo:[/bold cyan] [yellow]{uri}[/yellow]\n")
    console.print(generate_qr_ascii(uri))
    console.print("")


def main():
    app()


if __name__ == "__main__":
    main()


