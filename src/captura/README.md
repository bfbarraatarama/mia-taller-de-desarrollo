> **Nota de integración:** el código de producción se encuentra bajo `src/`. Los registros de diseño y evaluación históricos se conservan; para la instalación se utiliza el entorno general del README raíz.

# PoC · Paso 1: captura de reuniones

Graba el micrófono y el audio del sistema (la voz de los demás participantes) en un solo WAV mono de 16 kHz, listo para diarizar y transcribir. El archivo se escribe mientras se graba; ante una interrupción puede recuperarse al reiniciar la aplicación. Las mediciones previas se conservan en las notas técnicas.

## Instalación

Utilizar el entorno general de Python 3.12 descrito en el [README raíz](../../README.md#entorno-único-para-todo-el-repositorio). Allí se incluyen las dependencias de captura y los requisitos de PipeWire/JACK.

## Uso

```bash
pw-jack .venv/bin/python -m src.interfaz
pw-jack .venv/bin/python -m src.captura.captura --listar
pw-jack .venv/bin/python -m src.captura.captura --duracion 10 --tono
pw-jack .venv/bin/python -m src.captura.captura
.venv/bin/python -m src.captura.captura --mic "USB:0" --sistema "CABLE Output:0,1"
```

| Modo | Cómo elige las fuentes | Sistemas |
|---|---|---|
| Automático | Micrófono y salida por defecto de PipeWire | Linux con PipeWire |
| Manual | `--mic` y `--sistema` = `DISPOSITIVO[:canales]` (índice o parte del nombre: loopback, Stereo Mix, cable virtual, BlackHole) | Cualquiera |

En la interfaz: elegir las fuentes (Automático → Detectar, o Manual), presionar el botón rojo para grabar y otra vez para detener.

## Salida

En `resultados/grabaciones/` (configurable), con el nombre del momento en que empezó la grabación:

| Archivo | Contenido |
|---|---|
| `AAAA_MM_DD_HH_MM_SS.wav` | Micrófono + sistema, mono, 16 kHz, PCM 16 |
| `AAAA_MM_DD_HH_MM_SS.json` | Dispositivos, mediciones y 5 pruebas (señal en ambas fuentes, sin pérdidas, sin desincronización, salida procesable y tono). `"estado": "completa"`, o `"grabando…"` si se interrumpió |

## Archivos

| Archivo | Qué hace |
|---|---|
| `captura.py` | Grabación, remuestreo, mezcla, escritura incremental y reporte; se usa solo o desde la interfaz |
| `src/interfaz/interfaz.py` | Ventana principal (PySide6, estética Windows Vista) |
| `src/interfaz/panel_procesamiento.py` | Panel «Procesar reunión»: ejecuta el pipeline integrado |
| `src/interfaz/estilo.py` · `src/interfaz/widgets.py` | Hoja de estilo e íconos · encabezado, botón de grabar y medidores |
| `docs/captura/NOTAS-TECNICAS.md` | Escritura a prueba de cortes, criterios de las pruebas, mediciones en Fedora 43 y problema de eco |

## Problema conocido

Con parlantes, el micrófono vuelve a captar la voz de los demás: queda dos veces en el WAV (directa y como eco ~60 ms después). Con auriculares no debería ocurrir (no medido). Soluciones propuestas en [`docs/captura/NOTAS-TECNICAS.md`](../../docs/captura/NOTAS-TECNICAS.md#problema-conocido-el-audio-del-sistema-entra-por-el-micrófono-no-resuelto).
