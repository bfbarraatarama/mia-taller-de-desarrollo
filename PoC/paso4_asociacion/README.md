# PoC · Etapa 4: asociación y etiquetado de hablantes

Une `diarization.json` (Etapa 2) y `asr.json` (Etapa 3) sobre el mismo `audio.wav` en `transcription.json`: una lista de intervenciones con hablante, nombre, texto, tiempos y marcas de confianza, que la Etapa 5 lee sin transformaciones. Con interfaz, muestra una ficha por hablante para escuchar un fragmento y escribir su nombre.

Especificación, diseño y tareas: `openspec/changes/etapa-4-asociacion-etiquetado/`. Resultados de las pruebas: `registro-pruebas.md` en esa misma carpeta.

## Estado

| Grupo | Estado |
|---|---|
| 1 a 5 · contratos, asociación, marcas, fragmentos, modelo de las fichas | Hecho |
| 6 · diálogo y reproducción | Hecho; falta la lista de chequeo manual |
| 7 · panel de procesamiento | Hecha la 7.4; el resto espera acordar con la Etapa 5 las opciones `--hasta transcribir` y `--desde minuta` |
| 8 · datos reales en GPU | Hechas 8.1 a 8.3 (4 grabaciones propias, contrato al 100 %); falta la 8.4 con la Etapa 2 |
| 9 · muestra congelada | Pendiente (semana 7) |

## Instalación

| Uso | Necesita |
|---|---|
| Asociación por línea de comandos (`asociar.py`) | Python ≥ 3.12, solo biblioteca estándar. Corre en el entorno del orquestador sin instalar nada |
| Fichas (`fichas.py`) y ejemplo ideal | El `.venv` de la interfaz (`PoC/paso1_captura/requirements.txt`: PySide6, sounddevice, soundfile, NumPy, SciPy). El ejemplo ideal necesita además `espeak-ng` (`sudo dnf install espeak-ng` · `sudo apt install espeak-ng`) |
| Pruebas | `pytest` (`requirements-dev.txt`) |

```bash
# desde la raíz del repo, con el .venv de la interfaz ya creado
uv pip install --python .venv/bin/python -r PoC/paso4_asociacion/requirements-dev.txt
```

## Uso

Los comandos se corren desde `PoC/paso4_asociacion/`. Para no escribir la ruta del intérprete en cada uno:

```bash
PY="$(git rev-parse --show-toplevel)/.venv/bin/python"
```

**Sin interfaz** (orquestador): escribe `transcription.json` con `name: null` y no escribe `speakers.json`.

```bash
"$PY" asociar.py CARPETA_DE_LA_REUNION
"$PY" asociar.py --audio A.wav --diarizacion D.json --asr ASR.json --salida CARPETA
```

| Código de salida | Significado |
|---:|---|
| 0 | Escribió `transcription.json` y `transcription.meta.json` |
| 1 | Falló: el motivo va a la salida de errores y a `transcription.error.json`; el resultado anterior queda intacto |

**Con fichas** (prueba manual; el panel del paso 1 las va a abrir en el grupo 7):

```bash
"$PY" fichas.py CARPETA_DE_LA_REUNION   # 0 escribió · 1 falló · 2 cancelado, no escribió nada
```

**Desde Python** (API de D7):

```python
from asociacion import asociar
from etiquetado import aplicar
from fichas import etiquetar

a = asociar("CARPETA")         # valida y asocia; no escribe nada; lanza AsociacionError
aplicar(a, etiquetar(a))       # muestra las fichas y escribe según la decisión del usuario
```

**Ejemplo ideal** (D10): entradas perfectas, sintetizadas con espeak-ng, para probar sin las Etapas 2 y 3.

```bash
"$PY" ejemplo_ideal/generar.py                       # 3 hablantes, 60,8 s → ejemplo_ideal/generado/
"$PY" ejemplo_ideal/generar.py --guion ejemplo_ideal/guion_manual.json --salida ejemplo_ideal/generado/manual
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
| `fichas.py` | Diálogo de PySide6 y reproducción con sounddevice |
| `errores.py` | `AsociacionError`, con el paso en que falló |
| `ejemplo_ideal/` | Generador y guiones del ejemplo ideal |
| `evaluacion/` | Scripts de la medición de S26 citada en `design.md` |
| `tests/` | Un test por escenario de las specs |

## Pruebas

```bash
"$PY" -m pytest tests -q
```

Las pruebas cruzadas usan el código de las Etapas 2 (`PoC/paso2_diarizacion/`) y 5 (`src/minutas/`) del mismo repositorio. En el `.venv` de la interfaz se saltean las 2 de la Etapa 5, porque necesitan `pydantic`. Para correrlas, en el entorno 3.12 (ahí se saltea la de las fichas, porque necesita PySide6):

```bash
uv run --no-project --python 3.12 --with pytest --with pydantic --with numpy --with scipy --with soundfile \
  python -m pytest tests -q
```

Para probar contra otra copia de esas etapas: `ETAPA2_DIR=.../PoC/paso2_diarizacion` y `ETAPA5_SRC=.../src`.

Resultados medidos y lista de chequeo manual: `openspec/changes/etapa-4-asociacion-etiquetado/registro-pruebas.md`.
