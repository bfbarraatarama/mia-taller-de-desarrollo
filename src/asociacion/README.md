> **Integración:** los comandos de este documento utilizan la arquitectura actual. La tabla de estado y las especificaciones originales documentan el desarrollo previo a la integración.

# PoC · Etapa 4: asociación y etiquetado de hablantes

Une `diarization.json` (Etapa 2) y `asr.json` (Etapa 3) sobre el mismo `audio.wav` en `transcription.json`: una lista de intervenciones con hablante, nombre, texto, tiempos y marcas de confianza, que la Etapa 5 lee sin transformaciones. Con interfaz, muestra una ficha por hablante para escuchar un fragmento y escribir su nombre.

Especificación, diseño y tareas: `docs/asociacion/openspec/changes/etapa-4-asociacion-etiquetado/`. Resultados de las pruebas: `registro-pruebas.md` en esa misma carpeta.

## Estado

| Grupo | Estado |
|---|---|
| 1 a 5 · contratos, asociación, marcas, fragmentos, modelo de las fichas | Hecho |
| 6 · diálogo y reproducción | Hecho; falta la lista de chequeo manual |
| 7 · panel de procesamiento | Hecha la 7.4; el resto espera acordar con la Etapa 5 las opciones `--hasta transcribir` y `--desde minuta` |
| 8 · datos reales en GPU | Hechas 8.1 a 8.3 (4 grabaciones propias, contrato al 100 %); falta la 8.4 con la Etapa 2 |
| 9 · muestra congelada | Pendiente (semana 7) |

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

Reglas de asignación (`design.md`):
- **D1:** cada palabra va al hablante con más superposición.
- **D2:** un empate va al hablante de la palabra anterior; si no, al del turno más largo; si sigue, a la etiqueta menor.
- **D3:** una palabra en un hueco va al turno más cercano si está a 0,25 s o menos.
- **D4:** las intervenciones se cortan por cambio de hablante y en cada segmento de Whisper.
- **D5:** `overlap` marca 0,2 s o más con dos voces. `ambiguous` marca la falta de hablante, otra voz en el 30 % o más, o la propia en menos del 50 %.

La publicación es todo o nada: si algo falla a mitad, la carpeta vuelve al resultado anterior byte a byte.

## Archivos

| Archivo | Contenido |
|---|---|
| `contrato.py` | Validación de entradas y salidas (solo biblioteca estándar) |
| `asociacion.py` | `asociar()`: D1 a D5, sin escribir nada |
| `fragmentos.py` | D6: fragmento por hablante para las fichas |
| `etiquetado.py` | Modelo de las fichas, sin Qt: orden, nombres, cierre |
| `salida.py` | `escribir()`: publicación con respaldo y reversión, meta y errores |
| `asociar.py` | CLI sin interfaz |
| `src/interfaz/fichas.py` | Diálogo de PySide6 y reproducción con sounddevice |
| `errores.py` | `AsociacionError`, con el paso en que falló |
| `evaluacion/asociacion/ejemplo_ideal/` | Generador y guiones del ejemplo ideal |
| `evaluacion/asociacion/` | Scripts de la medición de S26 citada en `design.md` |
| `tests/asociacion/` | Un test por escenario de las specs |

## Pruebas

```bash
"$PY" -m pytest tests/asociacion -q
```

Las pruebas cruzadas utilizan `src.diarizacion` y `src.minutas` desde el entorno general. El ejemplo ideal requiere eSpeak NG; las fichas necesitan Qt y PortAudio.

Resultados medidos y lista de chequeo manual: `docs/asociacion/openspec/changes/etapa-4-asociacion-etiquetado/registro-pruebas.md`.
