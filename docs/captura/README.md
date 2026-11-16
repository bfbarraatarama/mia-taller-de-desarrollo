# Captura de reuniones

La decisión de conservar una única señal mixta evita depender de una plataforma de reuniones o de una pista por participante. No conserva las fuentes separadas, lo que limita la cancelación de eco y la atribución por canal. La alternativa multicanal queda fuera del alcance de esta PoC.

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

Si la grabación se interrumpe, la interfaz ofrece los WAV recuperables al iniciar. Agregarlos a la reunión o elegir no volver a avisar registra una decisión junto a cada grabación, sin alterar el reporte ni el WAV. Posponer el aviso no registra una decisión definitiva. Todas las grabaciones conservadas pueden cargarse manualmente. Véase [Reanudación y confidencialidad](../continuidad-y-confidencialidad.md#recuperación-de-grabaciones-interrumpidas).

## Archivos

| Archivo | Qué hace |
|---|---|
| `src/captura/captura.py` | Grabación, remuestreo, mezcla, escritura incremental y reporte; se usa solo o desde la interfaz |
| `src/interfaz/interfaz.py` | Ventana principal (PySide6; véase [diseño de interfaz](../interfaz-y-presentacion.md)) |
| `src/interfaz/panel_procesamiento.py` | Panel «Procesar reunión»: ejecuta el pipeline integrado |
| `src/interfaz/estilo.py` · `src/interfaz/widgets.py` | Paletas, estilo e íconos · encabezado, botón de grabar y medidores |
| `docs/captura/NOTAS-TECNICAS.md` | Escritura a prueba de cortes, criterios de las pruebas, mediciones en Fedora 43 y problema de eco |

## Problema conocido

Con parlantes, el micrófono vuelve a captar la voz de los demás: queda dos veces en el WAV (directa y como eco ~60 ms después). Con auriculares no debería ocurrir (no medido). Soluciones propuestas en [`docs/captura/NOTAS-TECNICAS.md`](NOTAS-TECNICAS.md#problema-conocido-el-audio-del-sistema-entra-por-el-micrófono-no-resuelto).
