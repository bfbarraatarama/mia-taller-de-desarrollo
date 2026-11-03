# PoC · Paso 1: captura de reuniones

Graba el micrófono y el audio del sistema (la voz de los demás participantes) en un solo WAV mono de 16 kHz, listo para diarizar y transcribir. El archivo se escribe mientras se graba: si la aplicación se corta, queda válido hasta los últimos ~0,3 s.

## Instalación

Desde la raíz del repo, con [uv](https://docs.astral.sh/uv/) y Python 3.14:

```bash
uv venv --python 3.14 .venv          # solo si no existe
uv pip install --python .venv/bin/python -r PoC/paso1_captura/requirements.txt
```

## Uso

```bash
.venv/bin/python PoC/paso1_captura/interfaz.py                         # interfaz gráfica
.venv/bin/python PoC/paso1_captura/captura.py --listar                 # ver dispositivos y detección
.venv/bin/python PoC/paso1_captura/captura.py --duracion 10 --tono     # prueba de 10 s con tono de 1 kHz
.venv/bin/python PoC/paso1_captura/captura.py                          # grabar hasta Ctrl+C
.venv/bin/python PoC/paso1_captura/captura.py --mic "USB:0" --sistema "CABLE Output:0,1"   # modo manual
```

| Modo | Cómo elige las fuentes | Sistemas |
|---|---|---|
| Automático | Micrófono y salida por defecto de PipeWire | Linux con PipeWire |
| Manual | `--mic` y `--sistema` = `DISPOSITIVO[:canales]` (índice o parte del nombre: loopback, Stereo Mix, cable virtual, BlackHole) | Cualquiera |

En la interfaz: elegir las fuentes (Automático → Detectar, o Manual), presionar el botón rojo para grabar y otra vez para detener.

## Salida

En `PoC/paso1_captura/grabaciones/` (configurable), con el nombre del momento en que empezó la grabación:

| Archivo | Contenido |
|---|---|
| `AAAA_MM_DD_HH_MM_SS.wav` | Micrófono + sistema, mono, 16 kHz, PCM 16 |
| `AAAA_MM_DD_HH_MM_SS.json` | Dispositivos, mediciones y 5 pruebas (señal en ambas fuentes, sin pérdidas, sin desincronización, salida procesable y tono). `"estado": "completa"`, o `"grabando…"` si se interrumpió |

## Archivos

| Archivo | Qué hace |
|---|---|
| `captura.py` | Grabación, remuestreo, mezcla, escritura incremental y reporte; se usa solo o desde la interfaz |
| `interfaz.py` | Ventana principal (PySide6, estética Windows Vista) |
| `panel_procesamiento.py` | Panel «Procesar reunión»: lanza el paso 2 (`PoC/paso2_procesamiento`, todavía no está en el repo) |
| `estilo.py` · `widgets.py` | Hoja de estilo e íconos · encabezado, botón de grabar y medidores |
| `NOTAS-TECNICAS.md` | Escritura a prueba de cortes, criterios de las pruebas, mediciones en Fedora 43 y problema de eco |

## Problema conocido

Con parlantes, el micrófono vuelve a captar la voz de los demás: queda dos veces en el WAV (directa y como eco ~60 ms después). Con auriculares no debería ocurrir (no medido). Soluciones propuestas en [`NOTAS-TECNICAS.md`](NOTAS-TECNICAS.md#problema-conocido-el-audio-del-sistema-entra-por-el-micrófono-no-resuelto).
