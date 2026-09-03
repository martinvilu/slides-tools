# slide-tools

Sistema de control remoto y telemetría bidireccional para Google Slides desde dispositivos externos (aplicación nativa Android y hardware embebido Wi-Fi operando en simultáneo) mediante una extensión de navegador WebExtensions y un daemon concentrador local/LAN.

Basado en la especificación técnica [spec.md](spec.md) (Versión 1.2).

---

## 🏛️ Arquitectura General

```
┌────────────────────────────────────────────────────────┐
│               Clientes Externos en LAN                 │
│  ┌───────────────────────┐   ┌──────────────────────┐  │
│  │  App Nativa Android   │   │  Hardware Wi-Fi      │  │
│  │  - Visor de notas     │   │  (ESP32 / RP2040W)   │  │
│  │  - Temporizador sync  │   │  - Botones físicos   │  │
│  │  - Control táctil     │   │  - Display OLED/LED  │  │
│  └───────────┬───────────┘   └──────────┬───────────┘  │
└──────────────┼──────────────────────────┼──────────────┘
               │                          │
               │ WebSocket LAN            │ WebSocket LAN
               │ (ws://<HOST_IP>:8766)    │ (ws://<HOST_IP>:8766)
               ▼                          ▼
┌────────────────────────────────────────────────────────┐
│             Daemon Local / Servidor de Enlace          │
│  - Enlace en 0.0.0.0:8766 (LAN + Loopback 127.0.0.1)   │
│  - Soporte multicliente con difusión broadcast de state│
│  - Emparejamiento por PIN/Token por sesión activa      │
│  - Temporizador emulado (fallback)                     │
└───────────────────────────┬────────────────────────────┘
                            │
                            │ WebSocket Loopback (ws://127.0.0.1:8766)
                            ▼
┌────────────────────────────────────────────────────────┐
│             Extensión Web (WebExtensions)              │
│       (Chromium / Firefox en docs.google.com)          │
│  ├─ Background Worker / Orchestrator                   │
│  ├─ Content Script: Pantalla Principal (/present)      │
│  │  ├─ Inyección teclado & Mini-Dock (PIN/Status/QR)   │
│  │  └─ Detección de diapositivas y títulos             │
│  └─ Content Script: Vista de Orador (Popup Window)     │
│     ├─ Extracción DOM de notas ricas y cronómetro      │
│     ├─ Inyección UI Toolbar compacta                   │
│     └─ Control bidireccional de pausa/reset timer      │
└────────────────────────────────────────────────────────┘
```

---

## 📦 Componentes del Sistema

1. **`slide_tools.daemon`**:
   - Servidor WebSocket multicliente enlazado en `0.0.0.0:8766`.
   - Administra el estado canónico de la presentación en memoria.
   - Seguridad mediante **código PIN de 4 dígitos** para emparejar clientes remotos.
   - Difunde en tiempo real (`broadcast`) cualquier cambio de diapositiva, notas o cronómetro a todos los clientes emparejados.
   - Cuenta con temporizador de respaldo en caso de que el usuario proyecte en pantalla completa estándar sin abrir la ventana de vista de orador.

2. **`extension/` (WebExtensions MV3)**:
   - Compatible con Google Chrome, Chromium, Brave, Edge y Firefox en URLs `https://docs.google.com/presentation/*`.
   - **`background.js`**: Conexión WebSocket resiliente con reconexión automática a `ws://127.0.0.1:8766`.
   - **`content-present.js`**: Dispara eventos sintéticos de teclado (`ArrowRight`, `ArrowLeft`, `Home`, `End`, `b`, `w`, `l`, dígitos numéricos + `Enter`) e inyecta el **Mini-Dock retráctil** con estado, PIN y botón de código QR.
   - **`content-speaker.js`**: Inspecciona el DOM de la ventana de notas (`.punch-speaker-notes-text`, `.punch-speaker-notes-timer-value`), limpia el texto plano UTF-8 para microcontroladores y controla los botones de pausa/reinicio del cronómetro nativo.
   - **`overlay.css`**: Estilos para el Mini-Dock, barra superior de vista de orador y modal de emparejamiento por QR.

3. **`slide_tools.cli` (`slide-tools`)**:
   - Interfaz de comandos para gestionar el daemon, inspeccionar telemetría en vivo, conmutar controles remotos o simular presentaciones para pruebas locales.

---

## 🚀 Instalación y Puesta en Marcha

### Requisitos

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/) instalado en el sistema

### 1. Iniciar el Daemon Concentrador

```bash
cd /home/mrtin/dev/tools/slide-tools
uv sync
uv run slide-tools daemon
```

Opciones:
- `--host` / `-h`: IP de enlace (por defecto `0.0.0.0`).
- `--port` / `-p`: Puerto TCP (por defecto `8766`).
- `--pin`: PIN de 4 dígitos fijo (si se omite, se genera aleatoriamente al iniciar).
- `--no-pin`: Modo permisivo para desarrollo sin validación de PIN.

### 2. Cargar la Extensión en el Navegador

#### Google Chrome / Chromium / Brave / Edge:
1. Navegá a `chrome://extensions/`.
2. Activá el **Modo de desarrollador**.
3. Hacé clic en **Cargar descomprimida**.
4. Seleccioná la carpeta `/home/mrtin/dev/tools/slide-tools/extension`.

#### Firefox:
1. Abrí `about:debugging#/runtime/this-firefox`.
2. Hacé clic en **Cargar complemento temporal**.
3. Seleccioná `/home/mrtin/dev/tools/slide-tools/extension/manifest.json`.

---

## 💻 Uso de la CLI (`slide-tools`)

```bash
# Ver estado consolidado de la presentación
uv run slide-tools status

# Navegación básica (requiere --pin <PIN> si el daemon lo solicita)
uv run slide-tools next --pin 4821         # Siguiente diapositiva o animación
uv run slide-tools prev --pin 4821         # Diapositiva anterior
uv run slide-tools first --pin 4821        # Primera diapositiva
uv run slide-tools last --pin 4821         # Última diapositiva
uv run slide-tools goto 14 --pin 4821      # Saltar a la diapositiva 14

# Efectos visuales de presentación
uv run slide-tools blackout --pin 4821     # Conmutar pantalla en negro (tecla b)
uv run slide-tools whiteout --pin 4821     # Conmutar pantalla en blanco (tecla w)
uv run slide-tools laser --pin 4821        # Conmutar puntero láser virtual (tecla l)

# Control del cronómetro
uv run slide-tools timer-reset --pin 4821  # Reiniciar temporizador
uv run slide-tools timer-pause --pin 4821  # Pausar o reanudar cronómetro

# Monitoreo continuo de eventos y notas en terminal
uv run slide-tools monitor --pin 4821

# Simular presentación para pruebas de hardware / app móvil sin navegador
uv run slide-tools mock-slides --slides 20
```

---

## 📡 Protocolo JSON v1.2

Estructura de paquete estándar:

```json
{
  "version": "1.2",
  "sessionId": "default",
  "source": "android" | "hardware" | "daemon" | "extension",
  "type": "command" | "state" | "event" | "ack" | "error",
  "action": "string",
  "payload": {}
}
```

### Telemetría de `STATE_SYNC`

```json
{
  "presentationTitle": "Plan de Operaciones 2026",
  "isPresenting": true,
  "presentationMode": "presenter_view",
  "currentSlide": 14,
  "totalSlides": 45,
  "isBlackout": false,
  "isWhiteout": false,
  "isLaserActive": false,
  "timer": {
    "elapsedSeconds": 754,
    "formattedTime": "12:34",
    "isPaused": false
  },
  "speakerNotes": {
    "hasNotes": true,
    "currentSlideNotes": "Enfatizar que la reducción de costos en la fase 2 no afecta los plazos."
  },
  "connectedClients": 2,
  "pin": "4821"
}
```

---

## 🧪 Pruebas Automatizadas

```bash
uv run pytest -v
```

---

## 📦 Empaquetado para Chrome y Firefox

Para empaquetar la extensión lista para cargar o distribuir:

```bash
uv run slide-tools pack
```

Opciones:
- `--target` / `-t`: `both` (por defecto), `chrome` o `firefox`.
- `--out-dir` / `-o`: Directorio de salida (por defecto `dist/`).

Archivos generados en `dist/`:
- **`slide-bridge-chrome-v1.2.0.zip`**: Manifiesto con `background.service_worker` para Chromium.
- **`slide-bridge-firefox-v1.2.0.xpi`**: Manifiesto con `background.scripts` y `browser_specific_settings.gecko` para Firefox MV3.
