# Manual de Uso y Referencia Técnica: slide-tools

> **SLIDE-TOOLS** — Sistema de control remoto y telemetría para Google Slides mediante WebExtensions y daemon concentrador local/LAN.
> **Versión:** `1.2.0` · **CLI principal:** `slide-tools` · **Plugin Ripley:** `slide-tools`

---

## 1. Arquitectura y Propósito Pedagógico

`slide-tools` forma parte del ecosistema de herramientas de la cátedra de Programación 1 (UNRN). Su objetivo central es resolver de forma modular, determinista y automatizada las tareas asociadas a su dominio específico dentro del ciclo de desarrollo, evaluación y aprendizaje de software en C.

### Principios de Diseño
- **Enfoque Pedagógico:** Diagnósticos y mensajes en español rioplatense orientados a facilitar la comprensión de errores conceptuales.
- **Salida Estructurada Dual:** Soporte nativo para visualización enriquecida en terminal (Rich) y salida parseable para orquestadores (`--json`).
- **Integración Contractual:** Capacidad de emitir secciones de reporte para `dredd` (`dredd-section`) y actuar como satélite orquestado por `ripley`.
- **Idempotencia y Robustez:** Validación de precondiciones y comandos de autodiagnóstico (`doctor`) para verificación del entorno.

---

## 2. Instalación y Requisitos

### Requisitos del Sistema
- **Python:** `>= 3.10` (recomendado Python 3.11 o 3.12).
- **Gestor de paquetes:** [`uv`](https://github.com/astral-sh/uv) (entorno estándar de cátedra).
- **Toolchain C (si aplica):** GCC / Clang, Make, GDB y bibliotecas estándar de desarrollo.

### Instalación en el Entorno de Usuario
Para instalar la herramienta de forma global y aislada en el sistema mediante `uv tool`:
```bash
uv tool install --editable /home/mrtin/dev/tools/slide-tools
```

### Verificación de Instalación
Ejecutá el comando `doctor` para constatar que todas las dependencias y binarios requeridos estén presentes y operativos:
```bash
slide-tools doctor
```

---

## 3. Guía Integral de Comandos (CLI)

| Comando | Descripción Breve |
| :--- | :--- |
| [`slide-tools daemon`](#daemon) | Inicia el daemon concentrador WebSocket en primer plano. |
| [`slide-tools status`](#status) | Muestra el estado consolidado de la presentación activa. |
| [`slide-tools next`](#next) | Avanza a la siguiente diapositiva o animación (NEXT_SLIDE). |
| [`slide-tools prev`](#prev) | Retrocede a la diapositiva o animación anterior (PREV_SLIDE). |
| [`slide-tools first`](#first) | Salta a la primera diapositiva (FIRST_SLIDE). |
| [`slide-tools last`](#last) | Salta a la última diapositiva (LAST_SLIDE). |
| [`slide-tools goto`](#goto) | Salta directamente a una diapositiva específica (GO_TO_SLIDE). |
| [`slide-tools blackout`](#blackout) | Conmuta pantalla en negro (TOGGLE_BLACKOUT). |
| [`slide-tools whiteout`](#whiteout) | Conmuta pantalla en blanco (TOGGLE_WHITEOUT). |
| [`slide-tools laser`](#laser) | Conmuta puntero láser virtual (TOGGLE_LASER). |
| [`slide-tools timer-reset`](#timerreset) | Reinicia el temporizador (TIMER_RESET). |
| [`slide-tools timer-pause`](#timerpause) | Pausa o reanuda el temporizador (TIMER_TOGGLE_PAUSE). |
| [`slide-tools monitor`](#monitor) | Monitorea en tiempo real cambios de diapositiva, notas y cronómetro. |
| [`slide-tools mock-slides`](#mockslides) | Simula una sesión de Google Slides conectada al daemon para pruebas. |
| [`slide-tools pack`](#pack) | Empaqueta la extensión WebExtensions para Chrome (.zip) y Firefox (.xpi). |
| [`slide-tools sign`](#sign) | Valida y firma digitalmente el addon para Firefox utilizando Mozilla web-ext. |
| [`slide-tools qr`](#qr) | Muestra el código QR para emparejamiento directo con la app Android. |
| [`slide-tools doctor`](#doctor) | Verifica el estado del entorno de SLIDE-TOOLS (Python, web-ext opcional). |

### `slide-tools daemon`

Inicia el daemon concentrador WebSocket en primer plano.

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--host`, `-h` | `<class 'str'>` | `127.0.0.1` | Dirección IP de escucha (127.0.0.1 por defecto; 0.0.0.0 para LAN) |
| `--port`, `-p` | `<class 'int'>` | `8766` | Puerto TCP WebSocket |
| `--pin` | `Optional[str]` | `None` | PIN de 4 dígitos fijo (si se omite, se genera aleatorio) |
| `--no-pin` | `<class 'bool'>` | `False` | Desactivar requerimiento de PIN (modo permisivo) |
| `--no-mdns` | `<class 'bool'>` | `False` | Desactivar publicación mDNS/Zeroconf |
| `--no-qr` | `<class 'bool'>` | `False` | Ocultar código QR en la consola |
| `--timeout`, `-t` | `<class 'float'>` | `2.5` | Timeout de respuesta de extensión |

#### Ejemplo de Invocación
```bash
slide-tools daemon
```

### `slide-tools status`

Muestra el estado consolidado de la presentación activa.

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | URI del daemon |
| `--json` | `<class 'bool'>` | `False` | Emitir el estado como JSON versionado (sin Rich). |

#### Ejemplo de Invocación
```bash
slide-tools status
```

### `slide-tools next`

Avanza a la siguiente diapositiva o animación (NEXT_SLIDE).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |
| `--pin`, `-k` | `Optional[str]` | `None` | - |

#### Ejemplo de Invocación
```bash
slide-tools next
```

### `slide-tools prev`

Retrocede a la diapositiva o animación anterior (PREV_SLIDE).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |
| `--pin`, `-k` | `Optional[str]` | `None` | - |

#### Ejemplo de Invocación
```bash
slide-tools prev
```

### `slide-tools first`

Salta a la primera diapositiva (FIRST_SLIDE).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |
| `--pin`, `-k` | `Optional[str]` | `None` | - |

#### Ejemplo de Invocación
```bash
slide-tools first
```

### `slide-tools last`

Salta a la última diapositiva (LAST_SLIDE).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |
| `--pin`, `-k` | `Optional[str]` | `None` | - |

#### Ejemplo de Invocación
```bash
slide-tools last
```

### `slide-tools goto`

Salta directamente a una diapositiva específica (GO_TO_SLIDE).

#### Argumentos
| Argumento | Tipo | Descripción |
| :--- | :--- | :--- |
| `slide` | `<class 'int'>` | Número de diapositiva de destino |

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |
| `--pin`, `-k` | `Optional[str]` | `None` | - |

#### Ejemplo de Invocación
```bash
slide-tools goto <slide>
```

### `slide-tools blackout`

Conmuta pantalla en negro (TOGGLE_BLACKOUT).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |
| `--pin`, `-k` | `Optional[str]` | `None` | - |

#### Ejemplo de Invocación
```bash
slide-tools blackout
```

### `slide-tools whiteout`

Conmuta pantalla en blanco (TOGGLE_WHITEOUT).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |
| `--pin`, `-k` | `Optional[str]` | `None` | - |

#### Ejemplo de Invocación
```bash
slide-tools whiteout
```

### `slide-tools laser`

Conmuta puntero láser virtual (TOGGLE_LASER).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |
| `--pin`, `-k` | `Optional[str]` | `None` | - |

#### Ejemplo de Invocación
```bash
slide-tools laser
```

### `slide-tools timer-reset`

Reinicia el temporizador (TIMER_RESET).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |
| `--pin`, `-k` | `Optional[str]` | `None` | - |

#### Ejemplo de Invocación
```bash
slide-tools timer-reset
```

### `slide-tools timer-pause`

Pausa o reanuda el temporizador (TIMER_TOGGLE_PAUSE).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |
| `--pin`, `-k` | `Optional[str]` | `None` | - |

#### Ejemplo de Invocación
```bash
slide-tools timer-pause
```

### `slide-tools monitor`

Monitorea en tiempo real cambios de diapositiva, notas y cronómetro.

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |
| `--pin`, `-k` | `Optional[str]` | `None` | - |
| `--json` | `<class 'bool'>` | `False` | Emitir cada evento como una línea JSON (NDJSON) versionada. |

#### Ejemplo de Invocación
```bash
slide-tools monitor
```

### `slide-tools mock-slides`

Simula una sesión de Google Slides conectada al daemon para pruebas.

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--slides`, `-s` | `<class 'int'>` | `10` | Cantidad de diapositivas simuladas |
| `--uri`, `-u` | `<class 'str'>` | `ws://127.0.0.1:8766` | - |

#### Ejemplo de Invocación
```bash
slide-tools mock-slides
```

### `slide-tools pack`

Empaqueta la extensión WebExtensions para Chrome (.zip) y Firefox (.xpi).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--target`, `-t` | `<class 'str'>` | `both` | Navegador objetivo: chrome, firefox o both |
| `--out-dir`, `-o` | `<class 'str'>` | `dist` | Directorio de salida para los paquetes |

#### Ejemplo de Invocación
```bash
slide-tools pack
```

### `slide-tools sign`

Valida y firma digitalmente el addon para Firefox utilizando Mozilla web-ext.

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--api-key`, `-k` | `Optional[str]` | `None` | API Key (JWT issuer) de Mozilla AMO |
| `--api-secret`, `-s` | `Optional[str]` | `None` | API Secret de Mozilla AMO |
| `--channel`, `-c` | `<class 'str'>` | `unlisted` | Canal de distribución: unlisted o listed |
| `--out-dir`, `-o` | `<class 'str'>` | `dist` | Directorio destino para el .xpi firmado |
| `--lint-only` | `<class 'bool'>` | `False` | Solo validar compatibilidad y manifiesto con web-ext lint |
| `--dry-run` | `<class 'bool'>` | `False` | Verificar manifiesto e imprimir el comando web-ext sign sin enviar |

#### Ejemplo de Invocación
```bash
slide-tools sign
```

### `slide-tools qr`

Muestra el código QR para emparejamiento directo con la app Android.

#### Argumentos
| Argumento | Tipo | Descripción |
| :--- | :--- | :--- |
| `pin` | `<class 'str'>` | PIN de emparejamiento |

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--port`, `-p` | `<class 'int'>` | `8766` | Puerto TCP WebSocket |
| `--host`, `-h` | `Optional[str]` | `None` | IP anfitrión (si se omite, se detecta automáticamente) |

#### Ejemplo de Invocación
```bash
slide-tools qr <pin>
```

### `slide-tools doctor`

Verifica el estado del entorno de SLIDE-TOOLS (Python, web-ext opcional).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--json` | `<class 'bool'>` | `False` | Emitir diagnóstico en formato JSON estructurado. |

#### Ejemplo de Invocación
```bash
slide-tools doctor
```

---

## 4. Formatos de Salida e Integración con el Ecosistema

### Modo Interactivo / Terminal (Rich)
Por defecto, la herramienta renderiza paneles, árboles y tablas estilizadas para facilitar la lectura del estudiante y docente en terminales modernas con soporte ANSI.

### Modo Estructurado JSON (`--json`)
Para integración con pipelines de CI/CD, scripts de automatización u orquestadores externos, la opción `--json` emite un documento JSON estricto por la salida estándar (`stdout`), dirigiendo cualquier mensaje de logging a `stderr`:
```bash
slide-tools daemon --json
```

### Integración con Dredd (`dredd-section`)
Cuando la herramienta genera reportes de evaluación para entregas de alumnos, produce una sección Markdown estandarizada conforme al contrato de integración de Dredd (v1.0.0):
```markdown
<!-- dredd-section: slide-tools, tool=slide-tools, version=1.2.0, status=ok -->
```
Este encabezado garantiza la agregación determinista de los hallazgos en la rúbrica docente.

### Integración con Ripley
`slide-tools` está registrada en el catálogo de plugins satélites de Ripley (`SATELLITE_CATALOG`). Puede invocarse directamente a través del motor de evaluación de Ripley configurando el análisis en `ripley.toml`.

---

## 5. Diagnóstico y Códigos de Salida

### Códigos de Retorno (`exit code`)
| Código | Significado |
| :---: | :--- |
| `0` | Ejecución exitosa sin hallazgos críticos ni errores de sintaxis. |
| `1` | Hallazgos pedagógicos detectados, infracción de reglas o advertencias activas. |
| `2` | Error de sintaxis en argumentos CLI o archivo fuente no encontrado. |
| `>2` | Error no recuperable del sistema, fallo de memoria o excepción interna. |

### Diagnóstico del Entorno (`doctor`)
Ante comportamientos inesperados, verificá el estado operativo con:
```bash
slide-tools doctor
```
Comprueba la presencia de las dependencias requeridas y la integridad de los componentes del paquete.