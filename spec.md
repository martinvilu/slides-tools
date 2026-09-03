# Documento de Especificación Técnica: Sistema de Control Remoto para Google Slides

**Versión:** 1.2

**Objetivo:** Permitir el control remoto y la telemetría bidireccional de presentaciones activas de Google Slides (navegación de diapositivas, pantalla negra/blanca, puntero láser, notas de orador y temporizador sincronizado) desde clientes externos (aplicación nativa Android y hardware embebido Wi-Fi operando de manera simultánea) mediante un daemon local por WebSocket y una extensión de navegador WebExtensions con inyección dual de interfaz (pantalla principal y vista de orador).

## 1\. Arquitectura General del Sistema

El sistema implementa una arquitectura cliente-servidor distribuida en red local (LAN/Loopback). Un daemon local residente en la computadora anfitriona centraliza la comunicación y permite la conexión concurrente de múltiples clientes de control (por ejemplo, un teléfono Android mostrando notas de orador mientras un clicker físico por hardware cambia las diapositivas).

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
│            (Node.js / Go / Python en la PC)            │
│  - Enlace en 0.0.0.0:8766 (LAN + Loopback 127.0.0.1)   │
│  - Soporte multicliente con difusión broadcast de state│
│  - Emparejamiento por PIN/Token por sesión activa      │
└───────────────────────────┬────────────────────────────┘
                            │
                            │ WebSocket Loopback (ws://127.0.0.1:8766)
                            ▼
┌────────────────────────────────────────────────────────┐
│             Extensión Web (WebExtensions)              │
│       (Chromium / Firefox en docs.google.com)          │
│  ├─ Background Worker / Orchestrator                   │
│  ├─ Content Script: Pantalla Principal (/present)      │
│  │  ├─ Inyección teclado & UI Overlay (PIN/Status)     │
│  │  └─ Fallback de notas/timer si no hay vista orador  │
│  └─ Content Script: Vista de Orador (Popup Window)     │
│     ├─ Extracción DOM de notas ricas y cronómetro      │
│     ├─ Inyección UI Overlay compacta (Estado/Pairing)  │
│     └─ Control bidireccional de pausa/reset timer      │
└────────────────────────────────────────────────────────┘
```

### Componentes del Sistema:

1.  **Clientes Externos (Uso Concurrente Soportado):**
    
    *   **App Nativa Android:** Interfaz táctil que muestra en tiempo real el número de diapositiva actual/total, notas del orador (_speaker notes_), temporizador sincronizado y controles de navegación.
        
    *   **Hardware Embebido Wi-Fi (ESP32 / RP2040W):** Dispositivo de mano con botones mecánicos de avance/retroceso, funciones auxiliares (láser, blackout) y retroalimentación de estado (LEDs o pantalla OLED de bajo consumo).
        
    *   **Concurrencia:** Ambos dispositivos pueden conectarse simultáneamente a la misma sesión; cualquier comando emitido por uno se refleja de inmediato en la telemetría recibida por el otro.
        
2.  **Daemon Local / Concentrador LAN:**
    
    *   Servidor WebSocket que escucha en `0.0.0.0:8766` para admitir tráfico local de la PC host (`127.0.0.1`) y de la red Wi-Fi local.
        
    *   Mantiene el estado canónico de la presentación en memoria. Cuando la extensión o cualquier cliente envía una actualización o comando, el daemon lo difunde (_broadcast_) a todos los clientes emparejados.
        
    *   Aislamiento seguro: Administra un código de emparejamiento (PIN) temporal generado por la extensión para rechazar clientes no autorizados en la red local.
        
3.  **Extensión Web (WebExtensions) con Soporte Multi-Ventana:**
    
    *   Se ejecuta en URLs `https://docs.google.com/presentation/*`.
        
    *   **Coordinación Multi-Contexto:** Coordina mensajes entre la ventana de proyección principal y la ventana emergente de notas mediante la API interna de mensajes de la extensión (`runtime.sendMessage`).
        
    *   Genera eventos de teclado sintéticos para cambiar diapositivas y alternar estados visuales (láser, pantalla negra).
        
    *   Lee periódicamente o por mutación del DOM: número de diapositiva, notas de orador y el reloj/temporizador de presentación.
        

## 2\. Protocolo de Comunicación (JSON over WebSocket)

Estructura genérica de mensaje:

```
{
  "version": "1.2",
  "sessionId": "string",
  "source": "android" | "hardware" | "daemon" | "extension",
  "type": "command" | "state" | "event" | "ack" | "error",
  "action": "string",
  "payload": {}
}
```

### 2.1. Comandos de Control (Clientes → Daemon → Extensión)

| 
`action`

 | 

Payload

 | 

Descripción

 |
| --- | --- | --- |
| 

`NEXT_SLIDE`

 | 

`{}`

 | 

Avanza a la siguiente diapositiva o animación.

 |
| 

`PREV_SLIDE`

 | 

`{}`

 | 

Retrocede a la diapositiva o animación anterior.

 |
| 

`FIRST_SLIDE`

 | 

`{}`

 | 

Salta a la diapositiva inicial.

 |
| 

`LAST_SLIDE`

 | 

`{}`

 | 

Salta a la diapositiva final.

 |
| 

`GO_TO_SLIDE`

 | 

`{"slideNumber": number}`

 | 

Salta a una diapositiva específica por su número.

 |
| 

`TOGGLE_BLACKOUT`

 | 

`{}`

 | 

Conmuta la pantalla en negro (tecla `b`).

 |
| 

`TOGGLE_WHITEOUT`

 | 

`{}`

 | 

Conmuta la pantalla en blanco (tecla `w`).

 |
| 

`TOGGLE_LASER`

 | 

`{}`

 | 

Conmuta el puntero láser virtual (tecla `l`).

 |
| 

`TIMER_RESET`

 | 

`{}`

 | 

Reinicia el temporizador de la presentación.

 |
| 

`TIMER_TOGGLE_PAUSE`

 | 

`{}`

 | 

Pausa o reanuda el temporizador de la presentación.

 |
| 

`GET_STATE`

 | 

`{}`

 | 

Solicita emisión inmediata de `STATE_SYNC`.

 |

### 2.2. Eventos y Telemetría (Extensión → Daemon → Clientes)

| 
`action`

 | 

Payload

 | 

Descripción

 |
| --- | --- | --- |
| 

`STATE_SYNC`

 | 

Ver esquema de telemetría

 | 

Estado consolidado de la presentación, notas y temporizador.

 |
| 

`PAIRING_REQUIRED`

 | 

`{"pin": string, "qrPayload": string}`

 | 

Notifica que se requiere validación por PIN.

 |
| 

`PAIRING_SUCCESS`

 | 

`{"clientId": string, "deviceType": string}`

 | 

Confirma vinculación de un cliente.

 |
| 

`COMMAND_ACK`

 | 

`{"action": string, "status": "ok" | "failed"}`

 | 

Confirmación de comando ejecutado.

 |

**Esquema de Payload de Telemetría (`STATE_SYNC`):** _Optimizado para transferencias livianas hacia microcontroladores y apps móviles (solo texto plano UTF-8 y números enteros)._

```
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
    "currentSlideNotes": "Enfatizar que la reducción de costos en la fase 2 no afecta los plazos de entrega."
  }
}
```

## 3\. Integración de la Interfaz Inyectada (Dual Overlay UI)

La extensión debe integrar elementos gráficos interactivos (overlay UI) tanto en la **pantalla principal de proyección** como en la **ventana de vista de orador**. Ambas interfaces sincronizan su estado y ofrecen acceso inmediato a la vinculación y diagnóstico.

```
PANTALLA PRINCIPAL (Proyección)            VENTANA DE VISTA DE ORADOR
┌───────────────────────────────┐          ┌───────────────────────────────┐
│                               │          │ [Miniatura] [Notas de Orador] │
│                               │          │                               │
│                               │          ├───────────────────────────────┤
│                               │          │ UI Inyectada (Header/Dock):   │
│                               │          │ [● Conectado (2)] [PIN: 4821] │
│ ┌───────────────────────────┐ │          │ [QR Toggle] [Reset Timer]     │
│ │ UI Inyectada (Dock Mini): │ │          └───────────────────────────────┘
│ │ [● 2 Disp.] [PIN: 4821]   │ │
│ │ [Expandir QR Pairing]     │ │
│ └───────────────────────────┘ │
└───────────────────────────────┘
```

### 3.1. Inyección en la Pantalla Principal (`/present` o `/fullscreen`)

*   **Ubicación y Comportamiento:** Widget retráctil o semi-transparente ubicado en una esquina inferior. Debe auto-ocultarse junto a la barra de controles nativa de Google Slides para no interferir con el público durante la presentación.
    
*   **Componentes:**
    
    *   Indicador de estado del Daemon (Conectado / Desconectado).
        
    *   Contador de clientes activos (ej. _"2 dispositivos: Android + HW"_).
        
    *   Código PIN visible en tamaño legible para emparejamiento rápido.
        
    *   Botón para desplegar modal con código QR grande (para escaneo desde la app Android).
        

### 3.2. Inyección en la Ventana de Vista de Orador (_Speaker Notes Popup_)

*   **Ubicación y Comportamiento:** Barra de herramientas persistente integrada en el encabezado o lateral del layout de la ventana de notas. Al ser una pantalla orientada exclusivamente al orador, los elementos pueden mantenerse visibles de forma continua.
    
*   **Componentes:**
    
    *   Indicador de sincronización de notas y temporizador.
        
    *   Visualizador persistente de PIN y botón de código QR.
        
    *   Lista de clientes conectados con capacidad para expulsar o desvincular un dispositivo.
        
    *   Indicador visual de comandos entrantes (destello visual sutil cuando el hardware externo cambia de slide).
        

## 4\. Estrategia Híbrida de Ejecución (Arquitectura 5.3.3)

El sistema opera bajo una **estrategia híbrida con prioridad dinámica en la Vista de Orador**:

```
                  ┌──────────────────────────────┐
                  │   Detección de Ventanas      │
                  │     de Google Slides         │
                  └──────────────┬───────────────┘
                                 │
                 ¿Existe ventana de Orador activa?
                                 │
                 ├───────────────┴───────────────┐
                 ▼ SÍ                            ▼ NO
    ┌─────────────────────────────┐  ┌─────────────────────────────┐
    │   Modo Híbrido Primario     │  │   Modo Estándar (Fallback)  │
    │  (Presenter View Activa)    │  │  (Solo Pantalla Completa)   │
    ├─────────────────────────────┤  ├─────────────────────────────┤
    │ - Comandos: Proyección      │  │ - Comandos: Proyección      │
    │ - Notas: DOM de Orador      │  │ - Notas: Caché / Inactivas  │
    │ - Timer: Cronómetro nativo  │  │ - Timer: Emulado en Daemon  │
    │ - UI: En ambas ventanas     │  │ - UI: En pantalla principal │
    └─────────────────────────────┘  └─────────────────────────────┘
```

### 4.1. Escenario A: Modo Vista de Orador Activo (Enlace Completo)

*   **Coordinación de Contextos:** La extensión detecta el popup de notas y lo vincula con la pestaña de presentación mediante el `tabId`.
    
*   **Telemetría Nativa:**
    
    *   Las notas de orador se extraen directamente del DOM de la ventana de notas (`.punch-speaker-notes-text`).
        
    *   El temporizador lee el reloj oficial de Google Slides (`.punch-speaker-notes-timer-value`), garantizando consistencia absoluta entre la PC, el móvil y la pantalla OLED del hardware.
        
*   **Comandos:** Los comandos de navegación (`NEXT_SLIDE`, `PREV_SLIDE`) se ejecutan inyectando los eventos de teclado en la ventana principal de proyección, mientras que los comandos de temporizador (`TIMER_RESET`, `TIMER_TOGGLE_PAUSE`) manipulan los botones nativos del popup de notas.
    

### 4.2. Escenario B: Modo Pantalla Completa Estándar (Fallback)

*   **Operación Reducida:** Si el orador opta por proyectar directamente sin abrir la ventana de orador:
    
    *   El control de navegación (adelante, atrás, láser, blackout) opera con total normalidad sobre la ventana principal.
        
    *   **Fallback de Notas:** Si la extensión tuvo acceso previo a la vista de edición (`/edit`), precarga las notas en memoria local; en caso contrario, reporta `hasNotes: false`.
        
    *   **Fallback de Temporizador:** El daemon inicia un contador de tiempo transcurrido propio y lo sincroniza hacia los clientes externos, simulando el cronómetro oficial.
        
*   Si en cualquier momento el usuario abre la ventana de orador, el sistema conmuta automáticamente al Escenario A sin reiniciar la conexión de los clientes externos.
    

## 5\. Mecanismos de Control e Inspección Técnica

### 5.1. Inyección de Comandos Sintéticos

El visor de Google Slides escucha eventos de teclado en la ventana activa (`window`) o en el elemento con foco:

```
function dispatchPresentationKey(code, key, keyCode) {
  const target = document.activeElement || window;
  const eventData = {
    key: key,
    code: code,
    keyCode: keyCode,
    which: keyCode,
    bubbles: true,
    cancelable: true,
    composed: true,
    view: window
  };

  target.dispatchEvent(new KeyboardEvent('keydown', eventData));
  target.dispatchEvent(new KeyboardEvent('keyup', eventData));
}
```

*   **Avance:** `dispatchPresentationKey('ArrowRight', 'ArrowRight', 39)` o `PageDown` (34).
    
*   **Retroceso:** `dispatchPresentationKey('ArrowLeft', 'ArrowLeft', 37)` o `PageUp` (33).
    
*   **Pantalla Negra / Blanca:** Envío de tecla `b` (66) o `w` (87).
    
*   **Puntero Láser:** Envío de tecla `l` (76).
    
*   **Salto Directo a Diapositiva:** Envío secuencial de los dígitos como eventos `keydown` numéricos seguido del evento `Enter` (13).
    

### 5.2. Detección de Estado, Notas y Temporizador Sincronizado

1.  **Número de Diapositiva y Total:**
    
    *   En el visor de diapositivas estándar: extraído de `input.punch-viewer-slide-number-input` y selectores adyacentes de conteo total.
        
    *   En la ventana de _Presenter View_: extraído del visor de miniaturas de la columna izquierda o del indicador numérico principal.
        
2.  **Notas de Orador (**_**Speaker Notes**_**):**
    
    *   Se capturan directamente del contenedor `.punch-speaker-notes-text` en la ventana emergente de presentador.
        
    *   La extensión limpia tags HTML superfluos mediante regex o `element.innerText`, transmitiendo texto plano codificado en UTF-8 para facilitar su recepción en microcontroladores y apps móviles.
        
3.  **Sincronización de Temporizador:**
    
    *   La extensión lee el valor renderizado en `.punch-speaker-notes-timer-value`.
        
    *   Los comandos `TIMER_RESET` y `TIMER_TOGGLE_PAUSE` interactúan directamente con los botones de pausa/reinicio del cronómetro nativo de Slides en la vista de orador.
        

## 6\. Gestión de Concurrencia Multicliente y Pairing

1.  **Topología de Difusión en Daemon:**
    
    *   Cada cliente WebSocket que se conecta (Android, microcontrolador, extensión) se registra en una tabla de descriptores de sesión asociados al ID de la presentación activa.
        
    *   Cuando el hardware envía un `NEXT_SLIDE`:
        
        1.  El daemon lo enruta a la extensión de navegador.
            
        2.  La extensión avanza la diapositiva y emite el nuevo `STATE_SYNC`.
            
        3.  El daemon retransmite inmediatamente ese `STATE_SYNC` a la app Android, actualizando las notas de orador y el número de diapositiva en tiempo real.
            
2.  **Flujo de Emparejamiento Seguro:**
    
    *   La interfaz inyectada (en la pantalla principal y en la vista de orador) muestra un **PIN de 4 dígitos** y un código QR con los metadatos de conexión (`IP`, `puerto`, `token`).
        
    *   **App Android:** Escanea el código QR desde cualquiera de las dos pantallas para emparejarse automáticamente.
        
    *   **Hardware Wi-Fi:** Se conecta ingresando el PIN mediante portal cautivo, configuración serial o botones con pantalla OLED integrada.

    
