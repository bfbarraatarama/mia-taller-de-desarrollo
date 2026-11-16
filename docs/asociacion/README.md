# Asociación y etiquetado de hablantes

Une `diarization.json` (Etapa 2) y `asr.json` (Etapa 3) sobre el mismo `audio.wav` en `transcription.json`: una lista de intervenciones con hablante, nombre, texto, tiempos y marcas de confianza, que la Etapa 5 lee sin transformaciones. Con interfaz, muestra una ficha por hablante para escuchar un fragmento y escribir su nombre.

Especificación, diseño y tareas: `docs/asociacion/openspec/changes/etapa-4-asociacion-etiquetado/`. Resultados de las pruebas: `registro-pruebas.md` en esa misma carpeta.

El [estado previo a la integración](estado-desarrollo.md) se conserva por separado.

## Instalación

Utilizar el entorno general del [README raíz](../../README.md#entorno-único-para-todo-el-repositorio), que incluye las pruebas y eSpeak NG para el ejemplo ideal.

## Uso

Los comandos se corren desde la raíz del repositorio. Para no escribir la ruta del intérprete en cada uno:

```bash
PY="$(git rev-parse --show-toplevel)/.venv/bin/python"
```

**Sin interfaz** (orquestador): escribe `transcription.json` con `name: null` y no escribe `speakers.json`.

```bash
"$PY" -m src.asociacion.asociar CARPETA_DE_LA_REUNION
"$PY" -m src.asociacion.asociar --audio A.wav --diarizacion D.json --asr ASR.json --salida CARPETA
```

| Código de salida | Significado |
|---:|---|
| 0 | Escribió `transcription.json` y `transcription.meta.json` |
| 1 | Falló: el motivo va a la salida de errores y a `transcription.error.json`; el resultado anterior queda intacto |

**Con fichas** (prueba manual; la interfaz integrada también las utiliza):

```bash
"$PY" -m src.interfaz.fichas CARPETA_DE_LA_REUNION   # 0 escribió · 1 falló · 2 cancelado, no escribió nada
```

**Desde Python** (API de D7):

```python
from src.asociacion.asociacion import asociar
from src.asociacion.etiquetado import aplicar
from src.interfaz.fichas import etiquetar

a = asociar("CARPETA")         # valida y asocia; no escribe nada; lanza AsociacionError
aplicar(a, etiquetar(a))       # muestra las fichas y escribe según la decisión del usuario
```

**Ejemplo ideal** (D10): entradas perfectas, sintetizadas con espeak-ng, para probar sin las Etapas 2 y 3.

```bash
"$PY" -m evaluacion.asociacion.ejemplo_ideal.generar                       # 3 hablantes, 60,8 s → evaluacion/asociacion/ejemplo_ideal/generado/
"$PY" -m evaluacion.asociacion.ejemplo_ideal.generar --guion evaluacion/asociacion/ejemplo_ideal/guion_manual.json --salida evaluacion/asociacion/ejemplo_ideal/generado/manual
                                                     # 8 hablantes, uno que nunca habla solo (lista manual)
```

## Contratos

| Archivo | Sentido | Formato |
|---|---|---|
| `audio.wav` | Entrada (Etapa 1) | WAV 16 kHz, mono, PCM16 |
| `diarization.json` | Entrada (Etapa 2) | `{"segments": [{start, end, speaker}]}`; mismas reglas que `validar_diarizacion` de la Etapa 2 |
| `asr.json` | Entrada (Etapa 3) | `{language, segments: [{start, end, text, words: [{word, start, end}]}]}`; fines admitidos hasta 1,0 s después del audio, recortados |
| `transcription.json` | Salida (Etapa 5) | `{"segments": [{start, end, speaker, name, text, overlap, ambiguous}]}` |
| `speakers.json` | Salida, solo con etiquetado | `{etiqueta: {name, clip_start, clip_end}}` |
| `transcription.meta.json` | Salida | Versión, fecha, SHA-256 de entradas y salidas, umbrales, semilla de los fragmentos, recortes y conteos |
| `transcription.error.json` | Salida, solo si falla | Paso, mensaje, archivo, violaciones y si queda un resultado anterior válido |

Reglas de asignación ([diseño original](openspec/changes/etapa-4-asociacion-etiquetado/design.md), con la precisión temporal posterior indicada en D4):
- **D1:** cada palabra va al hablante con más superposición.
- **D2:** un empate va al hablante de la palabra anterior; si no, al del turno más largo; si sigue, a la etiqueta menor.
- **D3:** una palabra en un hueco va al turno más cercano si está a 0,25 s o menos.
- **D4:** las intervenciones se cortan por cambio de hablante y en cada segmento de Whisper. Sus límites abarcan los intervalos de todas las palabras del grupo, sin alterar su orden textual. Véase [Temporalidad de la transcripción](../temporalidad-transcripcion.md).
- **D5:** `overlap` marca 0,2 s o más con dos voces. `ambiguous` marca la falta de hablante, otra voz en el 30 % o más, o la propia en menos del 50 %.

La publicación prepara archivos y respaldos; ante un fallo recuperable, intenta restaurar el resultado anterior. No es una transacción multiarchivo ante un corte abrupto ni garantiza restauración si también falla la escritura de respaldo. En el flujo integrado, la vigencia se determina con los contratos y hashes del orquestador.

Cuando un segmento de ASR contiene algunas palabras con tiempos utilizables, la asociación utiliza esas palabras; no recupera automáticamente el resto del texto del segmento. Si ninguna tiene tiempos utilizables, se usa el texto del segmento con su intervalo válido. Este comportamiento puede perder contenido reconocido, incluso una negación; el texto de ASR original se conserva, pero no se garantiza su preservación íntegra en la transcripción asociada. No se asignan tiempos ficticios para resolverlo. Es una limitación pendiente de diseño y evaluación (véase [temporalidad](../temporalidad-transcripcion.md)).

## Archivos

| Archivo | Contenido |
|---|---|
| `src/asociacion/contrato.py` | Validación de entradas y salidas (solo biblioteca estándar) |
| `src/asociacion/asociacion.py` | `asociar()`: D1 a D5, sin escribir nada |
| `src/asociacion/fragmentos.py` | D6: fragmento por hablante para las fichas |
| `src/asociacion/etiquetado.py` | Modelo de las fichas, sin Qt: orden, nombres, cierre |
| `src/asociacion/salida.py` | `escribir()`: publicación con respaldo y reversión, meta y errores |
| `src/asociacion/asociar.py` | CLI sin interfaz |
| `src/interfaz/fichas.py` | Diálogo de PySide6 y reproducción con sounddevice |
| `src/asociacion/errores.py` | `AsociacionError`, con el paso en que falló |
| `evaluacion/asociacion/ejemplo_ideal/` | Generador y guiones del ejemplo ideal |
| `evaluacion/asociacion/` | Scripts de la medición de S26 citada en `design.md` |
| `tests/asociacion/` | Un test por escenario de las specs |

## Pruebas

```bash
"$PY" -m pytest tests/asociacion -q
```

Las pruebas cruzadas utilizan `src.diarizacion` y `src.minutas` desde el entorno general. El ejemplo ideal requiere eSpeak NG; las fichas necesitan Qt y PortAudio.

Resultados medidos y lista de chequeo manual: `docs/asociacion/openspec/changes/etapa-4-asociacion-etiquetado/registro-pruebas.md`.
