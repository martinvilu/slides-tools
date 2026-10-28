# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
versiones según [SemVer](https://semver.org/lang/es/).

## [1.3.1] - 2026-10-28

### Corregido

- La extensión no se conectaba al daemon en Firefox: sin `content_security_policy`, Firefox aplica a las extensiones Manifest V3 un CSP con `upgrade-insecure-requests` que convierte `ws://127.0.0.1:8766` en `wss://`, y el daemon no habla TLS (sólo registraba «connection closed»). El manifest declara el CSP sin esa directiva. Reproducido y verificado con Firefox 158.


### Seguridad

- Cualquier conexión que dijera `source: extension` quedaba emparejada sin PIN y podía manejar la presentación desde la red: la extensión se empareja con el PIN como cualquier cliente (o es local).
- El saludo llevaba el PIN a cualquiera que se conectara: ahora sólo a conexiones emparejadas o locales.
- Cualquier página web abierta en el navegador podía conectarse al daemon en 127.0.0.1: ahora responde 403.
- PIN comparado en tiempo constante.

### Agregado

- Token de reconexión en `PAIRING_SUCCESS` (8 h, en memoria) que reemplaza al PIN en `PAIR_REQUEST`.
- `slide-tools atajos`: atajos de teclado globales (GNOME) para avanzar, retroceder, pantalla en negro y temporizador; `--notificar` en esos comandos.
- `slide-tools bandeja`: indicador de estado en la bandeja del sistema o notificaciones.
- Registro rotativo en `~/.local/state/p1/cast.log`.
- Variable `SLIDE_TOOLS_PIN` para un daemon de otro equipo.

### Cambiado

- Una conexión desde el mismo equipo sin origen web no necesita PIN (antes la CLI local lo pedía con `--pin`).

## [1.3.0] - 2026-09-28

Primera versión con registro de cambios; lo anterior está en el historial de git.

### Agregado

- **cli**: cumplir el contrato de línea de comandos de LINEAMIENTOS §3.2 (N-ECO-04) (`68a595e`)

### Corregido

- **seguridad**: PIN de emparejamiento de 6 dígitos con secrets (N-MEET-02) (`595b420`)

### Documentación

- agregar el texto de la licencia GPL-3.0-or-later que declara pyproject (N-ECO-06) (`c0c986b`)
- incorporar manual de uso integral y referencia tecnica (slide-tools) (`333b53e`)

### Mantenimiento

- **calidad**: verificar errores de Python y dependencias vulnerables (N-ECO-08, N-ECO-13) (`5544e09`)
- **deps**: declarar cast-tools-common como dependencia en lugar de cargarla por sys.path (N-SLIDE-01) (`5ad11ba`)
