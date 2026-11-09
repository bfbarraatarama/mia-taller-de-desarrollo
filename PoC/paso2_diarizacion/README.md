# PoC · Paso 2: diarización (Etapa 2)

Recibe el `audio.wav` normalizado de la Etapa 1 (16 kHz, mono, PCM16) y escribe `diarization.json`: quién habla y cuándo, con el modelo [`pyannote/speaker-diarization-community-1`](https://huggingface.co/pyannote/speaker-diarization-community-1). Corre igual en CPU y en GPU; elige el dispositivo al ejecutarse.

> **Estado (09/11/2026).** Las tareas están en [`openspec/changes/etapa-2-diarizacion/tasks.md`](openspec/changes/etapa-2-diarizacion/tasks.md).
> - **Hecho:**
>   - el módulo y las pruebas de nivel 1;
>   - la integración con la Etapa 1 (nivel 2, en CPU);
>   - la preparación del dataset de Figshare (S26, 25 grabaciones);
>   - la evaluación de calidad **en CPU**, reproducible con los JSON versionados: DER estricto 23,15 %, DER NIST 12,32 % y JER 40,02 %. Ver [`evaluacion/EVALUACION_S26.md`](evaluacion/EVALUACION_S26.md);
>   - la misma evaluación **en GPU (CUDA)**, informada por una compañera desde su equipo, con las mismas métricas globales (tarea 7.7). Sus archivos no están en el repositorio (ver [Pruebas en GPU](#pruebas-en-gpu-tareas-73-74-y-77)).
> - **Pendiente:**
>   - **7.3:** el test automatizado de CUDA (`tests/test_evaluacion_gpu.py`). La memoria se midió solo a mano.
>   - **7.4:** completar la verificación en GPU: `-m gpu`, el nivel 1 en el equipo con GPU y el registro de las versiones.
>   - **7.5:** revisión y validación del equipo con la Etapa 4.
>   - **6.9:** falta la verificación desde una instalación nueva (ver [Estado de la tarea 6.9](#estado-de-la-tarea-69)).

## Versiones verificadas

| Equipo | Quién | Verificado |
|---|---|---|
| Windows 11, CPU, Python 3.12.10, `torch 2.8.0+cpu` | máquina de desarrollo de la Etapa 2 | `verificar_entorno.py` sin fallas, nivel 1, nivel 2 y evaluación de S26 (07–09/11/2026) |
| Ubuntu 24.04, NVIDIA RTX 4060 Ti 16 GB, Python 3.12.3, `torch 2.8.0+cu128`, pyannote.audio 4.0.7 | **una compañera, en su equipo** (informado el 09/11/2026) | `verificar_entorno.py` sin fallas, inferencia CUDA y evaluación de S26 en CUDA. No informó qué FFmpeg usó ni si corrió el nivel 1 |

Las RTX 3050 de 6 GB del equipo, que son las máquinas de referencia del Hito 3, todavía no se verificaron.

| Componente | Versión | Dónde se fija |
|---|---|---|
| Python | 3.12.x (verificado 3.12.10) | `verificar_entorno.py` |
| PyTorch / torchaudio | 2.8.0 (`+cpu` o `+cu128`) | comando de instalación + `constraints.txt` |
| TorchCodec | 0.7.0 (serie 0.7, la de torch 2.8; carga FFmpeg **4 a 7**) | `requirements.txt` + `constraints.txt` |
| pyannote.audio | 4.0.7 | `requirements.txt` + `constraints.txt` |
| pyannote.metrics | 4.2.0 | `requirements.txt` + `constraints.txt` |
| Resto del árbol (98 paquetes) | versiones exactas | `constraints.txt` |
| FFmpeg | 7.1.1 *shared* (gyan.dev, Windows) | instalación local (ver abajo) |
| 7-Zip | 22.01 o posterior | solo para el dataset de Figshare (grupo 6) |

**Por qué hay dos archivos.** `requirements.txt` lista las dependencias directas, sin PyTorch, para que cada máquina elija su wheel (CPU o CUDA). `constraints.txt` fija todo el árbol verificado **sin instalar nada**. Sin él, pip reemplaza PyTorch 2.8 por uno más nuevo de PyPI, porque `pytorch-metric-learning` 3.x pide `torch>=2.14`. `==2.8.0` acepta tanto `2.8.0+cpu` como `2.8.0+cu128`. No cambiar estas versiones sin acuerdo del equipo.

## Instalación desde cero

Todo desde la **raíz del repo**. El entorno es propio de esta etapa: no es el `.venv` de la interfaz (etapas 1 y 4).

### 1. Requisitos del sistema

| | Windows | Linux |
|---|---|---|
| Python 3.12 | [python.org](https://www.python.org/downloads/) (incluye el lanzador `py`) | `sudo apt install python3.12 python3.12-venv` · `sudo dnf install python3.12` |
| FFmpeg 7.1.1 *shared* | paso 4 de esta guía | paso 4 de esta guía |
| GPU (solo máquinas con GPU) | driver NVIDIA reciente; `nvidia-smi` tiene que responder | ídem |
| 7-Zip (grupo 6) | [7-zip.org](https://www.7-zip.org/) | `sudo apt install 7zip` · `sudo dnf install p7zip-plugins` |

### 2. Crear el entorno

```powershell
# Windows (PowerShell)
py -3.12 -m venv PoC/paso2_diarizacion/.venv
$py = "PoC/paso2_diarizacion/.venv/Scripts/python.exe"
& $py -m pip install --upgrade pip
```

```bash
# Linux
python3.12 -m venv PoC/paso2_diarizacion/.venv
py=PoC/paso2_diarizacion/.venv/bin/python
$py -m pip install --upgrade pip
```

En los comandos de abajo, `$py` es ese Python (en PowerShell se antepone `&`: `& $py ...`).

### 3. Instalar PyTorch (elegir UNA variante) y el resto

```powershell
# a) Máquina SIN GPU (CPU):
& $py -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu

# b) Máquina CON GPU NVIDIA (CUDA 12.8):
& $py -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128

# Después, en las dos, SIEMPRE con -c:
& $py -m pip install -r PoC/paso2_diarizacion/requirements.txt -c PoC/paso2_diarizacion/constraints.txt
& $py -m pip check                                   # "No broken requirements found."
& $py -c "import torch; print(torch.__version__, torch.cuda.is_available())"
#   a) 2.8.0+cpu False        b) 2.8.0+cu128 True
```

Si `torch.__version__` da algo distinto de `2.8.0+cpu` o `2.8.0+cu128`, pip reemplazó PyTorch: probablemente se instaló sin `-c`. Hay que repetir el paso 3 completo.

### 4. FFmpeg 7.1.1 *shared*, sin modificar el PATH del sistema

pyannote 4 lee el audio con TorchCodec, que carga las **bibliotecas compartidas** de FFmpeg (no `ffmpeg.exe`). TorchCodec 0.7 solo acepta FFmpeg **4 a 7**: con una 8 o una 9 falla con `Could not find module '...libtorchcodec_core7.dll' (or one of its dependencies)`. Si en el sistema ya hay otra FFmpeg, no hace falta desinstalarla: la consola la sigue usando.

#### Windows (verificado)

1. **Descargar y comprobar** la build *shared* 7.1.1 de gyan.dev, desde su repositorio oficial en GitHub. Se instala en una carpeta del usuario, sin permisos de administrador:

   ```powershell
   $base = "$env:LOCALAPPDATA\ffmpeg7"
   New-Item -ItemType Directory -Force "$base\descarga" | Out-Null
   Invoke-WebRequest https://github.com/GyanD/codexffmpeg/releases/download/7.1.1/ffmpeg-7.1.1-full_build-shared.7z -OutFile "$base\descarga\ffmpeg-7.1.1-full_build-shared.7z"
   (Get-Item "$base\descarga\ffmpeg-7.1.1-full_build-shared.7z").Length                      # 46646819
   (Get-FileHash "$base\descarga\ffmpeg-7.1.1-full_build-shared.7z" -Algorithm SHA256).Hash
   #   B73E7ED754D7AAE42783BB3D768C33F0C8DBE53ED9859B7CF910A23D442780B3 (observado el 07/11/2026; gyan.dev no publica uno)
   & "$env:ProgramFiles\7-Zip\7z.exe" t "$base\descarga\ffmpeg-7.1.1-full_build-shared.7z"   # Everything is Ok
   & "$env:ProgramFiles\7-Zip\7z.exe" x "$base\descarga\ffmpeg-7.1.1-full_build-shared.7z" "-o$base"
   Get-ChildItem "$base\ffmpeg-7.1.1-full_build-shared\bin\avcodec-*.dll"                   # avcodec-61.dll
   ```

2. **Registrar la carpeta de DLL solo en este venv.** Poner `bin` en `PATH` **no funciona**: desde Python 3.8, Windows no busca en `PATH` las DLL de las que depende una extensión. Hay que registrarla con `os.add_dll_directory`. Lo hace un archivo `.pth` en `site-packages`, que Python ejecuta cada vez que arranca este entorno:

   ```powershell
   $linea = 'import os; _d = os.environ.get("DIARIZACION_FFMPEG_DLL_DIR") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "ffmpeg7", "ffmpeg-7.1.1-full_build-shared", "bin"); os.name == "nt" and os.path.isdir(_d) and os.add_dll_directory(_d)'
   Set-Content -Encoding ascii PoC/paso2_diarizacion/.venv/Lib/site-packages/ffmpeg_dll_dir.pth $linea
   ```

   La ruta se calcula al ejecutarse, así que el contenido es igual para todos los usuarios y es ASCII puro. Python 3.12 lee los `.pth` como `utf-8-sig`, así que también tolera el BOM que agrega `-Encoding utf8` en PowerShell 5.1 (comprobado). Lo importante es que la línea empiece con `import`: si no, Python la toma como una ruta y no la ejecuta.

   - Afecta **solo a este venv**: no cambia el `PATH` de Windows ni otras instalaciones de Python.
   - Para usar otra carpeta, se define `DIARIZACION_FFMPEG_DLL_DIR` en el entorno de la consola antes de ejecutar. Ponerla en `.env` no sirve, porque el `.pth` corre antes de que se lea.
   - Para deshacerlo, se borra `ffmpeg_dll_dir.pth`. Si se recrea el venv, hay que repetir este paso.

#### Linux

> Una compañera pasó `verificar_entorno.py` sin fallas en Ubuntu 24.04, lo que incluye la decodificación con TorchCodec, y corrió la evaluación en CUDA. No informó cuál de las dos opciones de FFmpeg de abajo usó.

TorchCodec carga `libavcodec.so.61` y las demás con el cargador del sistema.

1. Mirar `ffmpeg -version`. Si la FFmpeg de la distribución es de la serie **4 a 7** (por ejemplo, la 6.1 de Ubuntu 24.04), alcanza con ella: `sudo apt install ffmpeg` o `sudo dnf install ffmpeg`.
2. Si es 8 o más nueva, se puede usar una build *shared* 7.1 local (por ejemplo, `ffmpeg-n7.1-latest-linux64-gpl-shared-7.1.tar.xz` de [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases)) extraída en `~/.local/ffmpeg7`. Se expone **solo en la consola en la que se ejecuta**, con `export LD_LIBRARY_PATH="$HOME/.local/ffmpeg7/lib:$LD_LIBRARY_PATH"`, sin tocar la configuración del sistema.

El paso 6 confirma cuál de las dos funcionó.

### 5. Token personal de Hugging Face

1. Con tu cuenta, aceptá las condiciones de https://huggingface.co/pyannote/speaker-diarization-community-1.
2. Creá un token de tipo "Read" en https://huggingface.co/settings/tokens.
3. Copiá la plantilla de la raíz del repo y completá **tu** token:

   ```powershell
   Copy-Item .env.example .env      # Linux: cp .env.example .env
   # editar .env:  HF_TOKEN=hf_...
   ```

`.env` está en `.gitignore` y nunca se versiona; `.env.example` no tiene ningún valor real. El módulo busca `.env` subiendo desde la carpeta en la que se ejecuta, así que hay que correr los comandos desde la raíz del repo. También sirven `HF_TOKEN` en el entorno, que tiene prioridad, o `hf auth login`. El token nunca se imprime ni se guarda en los resultados. Después de la primera descarga, el modelo queda en la caché de Hugging Face.

### 6. Verificar el entorno

```powershell
& $py PoC/paso2_diarizacion/verificar_entorno.py                      # CPU
& $py PoC/paso2_diarizacion/verificar_entorno.py --gpu                # máquinas con GPU: exige CUDA
& $py PoC/paso2_diarizacion/verificar_entorno.py --wav ruta\audio.wav # además, decodificar un WAV real
& $py -m pytest PoC/paso2_diarizacion                                 # pruebas de nivel 1
```

`verificar_entorno.py` imprime OK, AVISO o FALLA por cada punto y termina con `0` si no hay fallas:

| Comprobación | Qué mira |
|---|---|
| Python | que sea 3.12.x |
| Versiones | las dependencias directas y los 98 paquetes del lock contra `constraints.txt`; avisa si hay paquetes fuera del lock |
| Importaciones | `torch`, `torchaudio`, `torchcodec`, `pyannote.audio`, `pyannote.metrics`, `dotenv`, `numpy` y `pandas`, sin el aviso "torchcodec is not installed correctly" |
| CPU/GPU | variante del wheel (`+cpu`/`+cu128`), `torch.cuda.is_available()`, nombre de la GPU; con `--gpu`, falla si no hay CUDA |
| FFmpeg | la FFmpeg de la consola (informativo); en Windows, que exista `ffmpeg_dll_dir.pth` y que la carpeta tenga `avcodec-*.dll` |
| Decodificación | TorchCodec decodifica un WAV sintético (y el de `--wav`) y la cantidad de muestras coincide con la cabecera |
| Token | que haya `HF_TOKEN` en el entorno o en `.env`, sin mostrarlo |

> El entorno de las etapas 2 y 3 se va a compartir con la Etapa 3 (Whisper); su ubicación definitiva está pendiente de acordar con Felipe.

## Uso

Línea de comandos (desde la raíz del repo):

```powershell
& $py PoC/paso2_diarizacion/diarizar.py PoC/paso1_captura/grabaciones/2026_11_07_10_00_00.wav
& $py PoC/paso2_diarizacion/diarizar.py audio.wav --device cpu --num-speakers 2 --salida resultados/reunion1
```

| Opción | Valor |
|---|---|
| `--device` | `auto` (por defecto: CUDA si está disponible, si no CPU), `cpu` (forzada), `cuda` (error si no hay CUDA; no pasa a CPU) |
| `--num-speakers` | opcional: cantidad exacta de hablantes. Sin ella, la estima pyannote. No cambia el contrato de salida |
| `--salida` | carpeta de resultados. Por defecto `<carpeta del audio>/<nombre del audio>/`, una por reunión |

Al terminar bien muestra cada etiqueta con su tiempo de habla, para revisarla a mano.

Como función:

```python
from diarizar import diarizar
from errores import DiarizacionError

try:
    r = diarizar("audio.wav", device="auto", num_speakers=None)
    print(r["carpeta"], r["hablantes"], r["dispositivo"])
except DiarizacionError as e:
    print(e.etapa, e.mensaje)        # e.archivo_error: ruta de diarization.error.json
```

### Contrato para quien la invoque (orquestador)

Decidir **por el código de salida o por la excepción**, nunca por la presencia de `diarization.json` (puede ser de una ejecución anterior):

| Código | Significado |
|---|---|
| `0` | éxito: `diarization.json` y `diarization.meta.json` son de esta ejecución |
| `1` | falló la ejecución (`DiarizacionError`); el detalle está en stderr y en `diarization.error.json` |
| `2` | parámetros inválidos |

Detener el flujo y ofrecer un nuevo intento le corresponde al orquestador.

## Archivos de resultados

En la carpeta de la reunión:

| Archivo | Cuándo | Contenido |
|---|---|---|
| `diarization.json` | solo en un éxito | `{"segments": [{"start", "end", "speaker"}]}`: segundos desde el inicio, `0 <= start < end <= duración`, ordenados por `start`, etiquetas `SPEAKER_NN`. Los solapamientos se conservan |
| `diarization.meta.json` | solo en un éxito | `run_id`, audio (ruta, duración, SHA-256), modo y dispositivo usado, GPU, modelo, versiones, `num_speakers`, `tolerancia_fin_s` (heredado), `exceso_fin_max_s`, hablantes, segmentos, corregidos, descartados, tiempo, `vram_pico_mib` (GPU) y `diarization_sha256` (el SHA-256 del `diarization.json` que acompaña) |
| `diarization.error.json` | solo en un fallo | `run_id`, fecha, etapa, tipo, mensaje, modo pedido, si se conservó un resultado anterior y su `run_id` |

- Un fallo **nunca** sobrescribe ni borra el `diarization.json` y el meta anteriores; un éxito posterior borra el `diarization.error.json`.
- **Publicación del par:** antes de reemplazarlo, el par vigente se copia a `*.bak`. Si falla la publicación de cualquiera de los dos archivos (disco lleno, permisos, archivo bloqueado), se restaura el par anterior, o se borra lo publicado si no había uno, y el error se registra con la etapa `escritura`. Queda el par anterior intacto o ningún par, nunca un JSON de una ejecución con el meta de otra.
- **Límite:** si el proceso se corta de golpe justo entre los dos reemplazos (corte de energía, proceso terminado a la fuerza), o si falla también la restauración, el par puede quedar inconsistente.
  - **Se detecta:** el `diarization_sha256` del meta no coincide con el JSON, así que el resultado no cuenta como vigente y `contrato.py --meta` lo informa.
  - **Cómo recuperarlo:** en la carpeta pueden quedar `diarization.json.<marca>.bak` y `diarization.meta.json.<marca>.bak`. Renombralos a sus nombres originales, o volvé a diarizar.
- Si el audio no existe o los parámetros son inválidos, no se crea nada.
- Etapas de error: `parametros`, `audio`, `token`, `dispositivo`, `modelo`, `decodificacion`, `ejecucion`, `contrato`, `escritura`.

### Normalización de los tiempos

Los tiempos se redondean a 3 decimales **sin superar nunca la duración real del WAV** (`D = nframes / 16000`). La regla es **recortar, no descartar**:

- **Se recorta** todo segmento con alguna parte dentro del audio, sea cual sea su exceso: un `end` mayor que `D` pasa a `D3` (la duración truncada a 3 decimales, que nunca supera `D`) y un `start` negativo pasa a `0.0`. Cuenta como corregido.
- **Se descarta** solo lo que no tiene ninguna parte dentro del audio (`start >= D` o `end <= 0`) o queda vacío (`start >= end`) tras redondear y recortar.

| Campo del meta | Qué registra |
|---|---|
| `segmentos_corregidos` | segmentos recortados que se escribieron |
| `segmentos_descartados` | segmentos que no se escribieron |
| `exceso_fin_max_s` | el mayor exceso recortado por el final (`end - D`); 0,0 si no hubo ninguno |
| `tolerancia_fin_s` | **campo heredado** (0,05 s), que se conserva por compatibilidad. **Ya no controla los descartes**: solo sirve de referencia para leer `exceso_fin_max_s` (un exceso mayor indica un recorte por encima del redondeo habitual de frames) |

**Por qué recortar.** pyannote puede extender el último segmento algunas centésimas más allá del final del archivo, por la resolución de sus ventanas de análisis. Antes del 08/11/2026, todo exceso mayor a 0,05 s se descartaba. En una grabación interrumpida de 32,5 s, eso borró un tramo de habla real de 6 s, que pyannote había devuelto como 26,59–32,60 s. Ahora ese tramo se escribe como 26,592–32,5 s. El contrato de `diarization.json` no cambió.

Esto no afecta a la tolerancia de 0,01 s del Hito 2, que es de las anotaciones de referencia de Figshare.

## Validador del contrato

Solo usa la biblioteca estándar: sirve también desde el entorno de la interfaz (Etapa 4, script de contratos de 2.3).

```powershell
python PoC/paso2_diarizacion/contrato.py diarization.json audio.wav
python PoC/paso2_diarizacion/contrato.py diarization.json audio.wav --meta diarization.meta.json
```

Informa cada violación con su ubicación (`segments[3]: end=... supera la duración...`) y termina con `0` si no hay ninguna o `1` si las hay. Con `--meta` comprueba además que el JSON y el meta son de la misma ejecución.

## Pruebas

```powershell
& $py -m pytest PoC/paso2_diarizacion            # nivel 1: sin modelo ni GPU, en cualquier máquina
& $py -m pytest PoC/paso2_diarizacion -m "slow or gpu" -rs   # qué falta para los niveles 2 y 3
& $py -m pytest PoC/paso2_diarizacion -k integracion         # bloque A con archivos sintéticos (nivel 1)
```

| Nivel | Marker | Dónde corre |
|---|---|---|
| 1. Unitarias (contrato, normalización, entrada, token, dispositivo, resultados, errores, CLI, bloque A sintético) | ninguno | cualquier máquina, también sin GPU |
| 2. Integración Etapa 1 → Etapa 2 en CPU | `slow` | máquina de desarrollo sin GPU (grupo 5). Requiere `$env:DIARIZACION_AUDIOS_CPU = (Resolve-Path PoC/paso1_captura/grabaciones/nivel2).Path` |
| 3a. Calidad con Figshare (DER, JER, cantidad de hablantes) | `calidad` | **CPU o GPU**. Requiere el dataset preparado (`--preparar`); si falta, se saltea con el motivo |
| 3b. Pruebas propias de CUDA (memoria, `dispositivo: cuda`, compatibilidad CPU/GPU) | `gpu` (pendiente, tarea 7.3) | equipo con GPU NVIDIA (otro integrante) |

### Verificación básica del nivel 2 (tarea 5.5)

Verificación **automática** sobre las tres grabaciones de `PoC/paso1_captura/grabaciones/nivel2/`. Los datos salen de `tests/reportes/integracion_*.json` y de los `diarization.json` de `nivel2/<nombre>/`. No hay revisión auditiva obligatoria.

**Evidencia versionada:** [`evaluacion/resultados/nivel2/`](evaluacion/resultados/nivel2/) guarda copias de los tres reportes, `integracion_<grabacion>.json`. Cada uno tiene:
- la grabación, el estado de la Etapa 1, la duración y el dispositivo;
- el `tiempo_s`, los hablantes y los segmentos (corregidos y descartados);
- por hablante, la cantidad de segmentos, el tiempo de habla y los primeros segmentos.

No tienen audio ni rutas locales, y se revisó que no incluyan datos personales. `tests/reportes/` sigue fuera de git; estas copias se hacen a mano.

> **Corrida de origen.** Las copias son de la **re-ejecución del nivel 2 del 08/11/2026** (19:27–19:30, `run_id` `20261108T192726-26f561`, `20261108T192837-964c08` y `20261108T193009-3d0ea3`), hecha para verificar la tarea 6.9. Esa corrida reemplazó a los reportes originales de la tarea 5.3.
> - **Coinciden con la tabla:** sus `diarization.json` son **byte a byte idénticos** a los de la corrida original, así que los hablantes, los segmentos y el contenido de la tabla de abajo coinciden.
> - **Lo único distinto es el tiempo de inferencia:** es otra corrida en la misma CPU, con otra carga del equipo. La tabla de abajo conserva los **valores históricos de la corrida original**:
>
> | Grabación | `tiempo_s`, corrida original (tarea 5.3, en la tabla de abajo) | `tiempo_s`, re-ejecución de las 19:27–19:30 (reportes versionados) |
> |---|---|---|
> | `2026_11_08_09_21_37` | 63,71 s | 68,35 s |
> | `2026_11_08_09_35_54` | 49,51 s | 82,82 s |
> | `2026_11_08_11_41_26` | 31,91 s | 194,27 s |

**Cómo se calcula:**
- **Predominante por bloque:** se divide cada grabación en los bloques de unos 15 s de la secuencia diseñada. En cada bloque se suma, por speaker, el solapamiento de sus segmentos con el bloque, y el predominante es el speaker con más tiempo.
- **Mapeo:** a cada hablante esperado le corresponde el predominante de su primer bloque.
- **Anomalías:** segmentos de menos de 0,5 s, superposiciones entre speakers, tiempo de un speaker no predominante dentro de un bloque y desvíos de más de 0,5 s en un cambio de hablante.

| Grabación | Escenario | Etapa 1 | Hablantes esperados / detectados | Predominante por bloque (bloque 1 · 2 · 3) | Bloques coherentes | Reidentificación de A | Segmentos | Anomalías | Desvío en los cambios | `tiempo_s` (corrida original, tarea 5.3) |
|---|---|---|---|---|---|---|---|---|---|---|
| `2026_11_08_09_21_37` | auriculares (A · B · A) | completa | 2 / 2 | SPEAKER_01 99,2 % · SPEAKER_00 85,0 % · SPEAKER_01 100 % | 3 de 3 | sí | 13 | 12 (6 segmentos < 0,5 s, 2 superposiciones, 2 de speaker no predominante, 2 desvíos) | A → B: el turno de B empieza en 16,012 s (+1,01 s) · B → A: el turno de A empieza en 29,039 s (−0,96 s) | 63,71 s |
| `2026_11_08_09_35_54` | parlantes (A · B · A) | completa | 2 / 2 | SPEAKER_00 100 % · SPEAKER_01 84,2 % · SPEAKER_00 96,9 % | 3 de 3 | sí | 9 | 4 (2 de speaker no predominante, 2 desvíos) | A → B: A termina en 17,092 s y B empieza en 18,290 s (+3,29 s) · B → A: el turno de A empieza en 31,199 s (+1,20 s) | 49,51 s |
| `2026_11_08_11_41_26` | cierre forzado (una sola voz) | grabando (interrumpida) | 1 / 1 | SPEAKER_00 100 % en los tres bloques | 3 de 3 | — | 8 | 0 | sin cambios esperados; el último segmento llega al corte (32,5 s) | 31,91 s |

**Resultado:** en las tres grabaciones, la cantidad de hablantes detectada coincide con el diseño, el predominante de cada bloque es coherente con la secuencia y la persona A se reidentifica. Las discrepancias pequeñas quedan como anomalías. Los desvíos en los cambios de hablante no se separan del error de la referencia, porque los bordes de 15 y 30 s se tomaron a mano.

**Limitaciones: esto no es una evaluación de calidad.**
1. **Sesgo de diseño:** la secuencia de hablantes se conocía de antemano, y la verificación por bloques la usa para deducir el mapeo. Confirma un comportamiento básico, pero no mide precisión de forma independiente.
2. **Sin referencia exacta:** no hay anotación con tiempos de cada turno. Los bordes esperados (15 y 30 s) son aproximados.
3. **Muestra mínima:** 3 grabaciones con 2 hablantes como mucho (una con una sola voz); la voz B es un video, y nada de esto es una reunión.
4. **Condiciones de una sola máquina:** micrófono Realtek con cancelación de eco y Mezcla estéreo, en Windows.
5. **No se mide** DER, JER, confusión de hablantes ni el comportamiento con 3 o más hablantes. Eso es el nivel 3 (Figshare, grupos 6 y 7).

## Tolerancias

| Tolerancia | Valor | De qué es | Dónde se aplica |
|---|---|---|---|
| `tolerancia_fin_s` (salida) | 0,05 s | campo heredado del meta de `diarization.json` | solo se registra; los tiempos se recortan siempre a la duración real (ver "Normalización de los tiempos") |
| `TOLERANCIA_FIN_FIGSHARE_S` (referencia) | 0,01 s | exceso terminal admitido en las anotaciones de Figshare; **se importa** de `hito-2/scripts/validar_muestra.py` | una grabación cuyo `.phrases` termina más de 0,01 s después del WAV se excluye; si termina 0,01 s o menos después, su fin se ajusta a la duración real en la referencia y el ajuste se registra |
| orden | 1e-4 s | `start >= fin_anterior - 1e-4` (criterio del Hito 2) | validación de las anotaciones |
| NIST | ±0,25 s por lado (`collar=0.5` en pyannote) | `der_tolerancia` | evaluación de calidad (nivel 3a) |

## Dataset de test (Figshare, sesión S26)

Prepara la referencia para medir DER y JER con UBA Games (Figshare v2, CC BY 4.0). Por ahora la selección es **solo `s26.objects.04`** (52,271 s, 2 hablantes). Usa los archivos **ya descargados y extraídos** en `hito-2/.cache/uba_games/figshare-v2/`: no descarga, no extrae y no modifica nada de esa carpeta.

**7-Zip** se usa solo para **listar** los RAR (`7z l -slt`), nunca para extraer. Se busca la variable `SIETE_ZIP`, después `7z`/`7zz`/`7za` en el `PATH` y por último `%ProgramFiles%\7-Zip\7z.exe`. Si no está, el mensaje explica cómo instalarlo.

Desde la raíz del repo (`-X utf8` evita problemas de consola en Windows):

```powershell
$py = "PoC/paso2_diarizacion/.venv/Scripts/python.exe"
& $py -X utf8 PoC/paso2_diarizacion/evaluacion/preparar_figshare.py --verificar-entradas  # RAR y extraídos (solo lectura)
& $py -X utf8 PoC/paso2_diarizacion/evaluacion/preparar_figshare.py --validar             # + validez de cada grabación
& $py -X utf8 PoC/paso2_diarizacion/evaluacion/preparar_figshare.py --inventario          # etiquetas sin letras y su clase
& $py -X utf8 PoC/paso2_diarizacion/evaluacion/preparar_figshare.py --preparar            # escribe mono, RTTM y manifiesto
& $py -X utf8 PoC/paso2_diarizacion/evaluacion/preparar_figshare.py --verificar           # derivados contra el manifiesto
```

Todas aceptan `--seleccion 04 05 …`. Ampliar la selección cambia el manifiesto y **requiere autorización**. Además, las etiquetas `-?` (tarea 09) y `?-` (tarea 12) tienen que estar clasificadas en `evaluacion/politica_etiquetas.json`, con aprobación del equipo.

**Pasos de `--preparar`.** Si algo falla, no se escribe nada.
1. Verifica `phrases.rar` y `wavs.rar` contra `hito-2/fuentes.toml` (bytes y MD5) y `fuentes.lock.json` (SHA-256).
2. Verifica cada archivo usado de `extraidos/` (tamaño y CRC32) contra el listado de su RAR y calcula su SHA-256.
3. Valida cada grabación. Las que no cumplen quedan `excluida`, con su motivo:
   - WAV completo estéreo, de 16 kHz y PCM16, leído completo;
   - anotaciones de los dos canales bien formadas;
   - exceso terminal de 0,01 s o menos;
   - correspondencia canal ↔ hablante: cada canal se correlaciona más con su `wavs/S26/…channelN.wav` que con el otro.
4. Escribe en `PoC/paso2_diarizacion/datos/figshare_test/S26/`, que git ignora:
   - `<recording_id>.wav`, el mono `(izquierda + derecha) // 2`, de 16 kHz, PCM16 y con los mismos cuadros, que es la entrada de pyannote;
   - `<recording_id>.rttm`, con los hablantes `figshare_v2_S26_canal1` y `figshare_v2_S26_canal2`:
     - `#` se excluye y el texto con letras es habla;
     - las etiquetas sin letras siguen la política;
     - los intervalos del mismo canal superpuestos o contiguos se unen;
     - el solapamiento entre canales se conserva;
     - los tiempos tienen 3 decimales y nunca superan la duración real.
5. Calcula el **indicador de cobertura** por canal. Es solo un indicio y no cambia la referencia. Busca dos cosas:
   - energía alta dentro de un `#` y fuera de la habla del otro canal, en tramos de 0,3 s o más;
   - habla anotada con energía baja.
6. Escribe `evaluacion/figshare_test.manifest.json`, que se versiona y no contiene el texto de las anotaciones. Tiene dos secciones:
   - `contenido`: determinista, con su `contenido_sha256`;
   - `ejecucion`: fecha, sistema, Python, 7-Zip y commit, que no se comparan.

`--verificar` recalcula `contenido_sha256` y los SHA-256 del mono y del RTTM. Si algo no coincide, falla nombrando la grabación. El nivel 3 lo ejecuta antes de evaluar.

**Resultado con `s26.objects.04` (08/11/2026):**
- Grabación válida: 836 333 cuadros.
- Correlación de cada canal con su WAV separado: 0,99996 y 0,99999.
- Exceso terminal: 0,0092 s en los dos canales. Los dos excesos están en intervalos `#`, así que no hubo ajustes.
- Referencia: 33 segmentos (15 del canal 1 y 18 del canal 2), utilizable.
- Cobertura: 0 s de posible habla sin anotar. La proporción de habla anotada con energía baja es 8,6 % en el canal 1 y 6,6 % en el canal 2. Probablemente son pausas dentro de las frases, pero no se revisó a mano.
- `contenido_sha256` = `3a5323680f095f7ae2545da0cd2c3d10a09488f3ee7a9712b37bed75d2783ec3`.

## Evaluación de calidad (nivel 3a)

```powershell
& $py -m pytest PoC/paso2_diarizacion -m calidad -rs                 # corrida principal (sin num_speakers)
& $py -m pytest PoC/paso2_diarizacion -m calidad -rs --diagnostico   # además, la diagnóstica con num_speakers=2
```

Primero ejecuta `--verificar`. Después diariza con `device="auto"` el WAV mono de cada grabación válida del manifiesto y compara la salida con el RTTM. La región evaluada (UEM) es `[0, duración]`, y el habla superpuesta se incluye en las tres métricas.

| Métrica | Qué es | Parámetros de `pyannote.metrics` |
|---|---|---|
| `der_estricto` | DER sin tolerancia: cada borde cuenta | `DiarizationErrorRate(collar=0.0, skip_overlap=False)` |
| `der_tolerancia` | **DER de pyannote.metrics con tolerancia NIST** de ±0,25 s por borde. **No** es un resultado de `md-eval`: reproduce su tolerancia por lado, pero no garantiza los mismos valores | `DiarizationErrorRate(collar=0.5, skip_overlap=False)` (en pyannote, `collar` es el ancho total) |
| `jer` | Jaccard Error Rate, con el error de cada hablante de la referencia | `JaccardErrorRate(collar=0.0, skip_overlap=False)` |

Cada DER trae sus componentes en segundos y como proporción de `total_referencia_s`: `falsa_alarma_s`, `habla_perdida_s` y `confusion_s`. El reporte trae además la cantidad de hablantes (referencia, detectados y si coinciden) y, con dos grabaciones o más, la dispersión: mediana, cuartiles y peor grabación. No hay umbral; los valores son la línea de base de la PoC.

Reportes, ignorados por git:
- `tests/reportes/calidad_S26.json`: por grabación y acumulado de la sesión;
- `tests/reportes/calidad_total.json`: acumulado, dispersión, cantidad de hablantes y `limitaciones`, que incluye el indicador de cobertura.

Las salidas de pyannote quedan en `tests/reportes/calidad/<recording_id>/<corrida>/`.

**Resultados de S26** (25 grabaciones, detección automática de hablantes): metodología, tabla por grabación, análisis de errores y limitaciones en [`evaluacion/EVALUACION_S26.md`](evaluacion/EVALUACION_S26.md).
- **CPU, reproducible:** los reportes y las hipótesis versionados en `evaluacion/resultados/` son de la corrida en CPU. Se generan con `evaluacion/publicar_resultados.py`, y la prueba `-k resultados_publicados` recalcula las métricas desde esos archivos sin correr el modelo.
- **GPU, informado:** una compañera repitió la evaluación en CUDA y obtuvo las mismas métricas globales. Sus reportes no están versionados, así que no se pueden recalcular desde el repositorio (ver [Pruebas en GPU](#pruebas-en-gpu-tareas-73-74-y-77)).

## Qué corre sin GPU y qué en el equipo con GPU

| Qué | Sin GPU (máquina de desarrollo) | Con GPU NVIDIA |
|---|---|---|
| Instalación (`requirements.txt` + `constraints.txt`) | PyTorch `2.8.0+cpu` | PyTorch `2.8.0+cu128` |
| `verificar_entorno.py` | sí | sí, con `--gpu` |
| Nivel 1 (unitarias, sin modelo) | sí | sí |
| Nivel 2 (Etapa 1 → Etapa 2, `-m slow`) | sí (verificado) | sí |
| Preparación y `--verificar` del dataset de Figshare | sí (verificado; no usa el modelo) | sí |
| Nivel 3a, calidad DER/JER (`calidad`, tareas 7.2, 7.6 y 7.7) | sí (verificado: S26 completo, 2333,6 s de inferencia) | sí (informado por una compañera: S26 completo en CUDA, 79,1 s de inferencia) |
| Nivel 3b, pruebas de CUDA (`gpu`, tarea 7.3: memoria, `dispositivo: cuda`, CPU vs GPU) | no (se saltean) | **pendiente**: el test todavía no existe |

### Pruebas en GPU (tareas 7.3, 7.4 y 7.7)

La máquina de desarrollo de la Etapa 2 solo tiene CPU. Las pruebas en GPU las hizo **una compañera en su equipo** y las informó en su revisión del PR #8. **Sus archivos (reportes de calidad, hipótesis y salida de `verificar_entorno.py`) no están en el repositorio**, así que estos valores son evidencia informada, no reproducible desde los JSON versionados. El detalle está en [`registro-pruebas.md`](openspec/changes/etapa-2-diarizacion/registro-pruebas.md), sección "Pruebas en GPU".

| Medida | CPU (máquina de desarrollo, reproducible) | GPU (compañera, informado) |
|---|---|---|
| Equipo | Windows 11, `torch 2.8.0+cpu` | Ubuntu 24.04, RTX 4060 Ti 16 GB, `torch 2.8.0+cu128` |
| Grabaciones de S26 | 25/25 (la 04 reutilizada de una corrida compatible) | 25/25 en CUDA, sin reutilizar |
| DER estricto | 23,15 % | 23,15 % |
| DER NIST (±0,25 s) | 12,32 % | 12,32 % |
| JER | 40,02 % | 40,02 % |
| Cantidad de hablantes correcta | 24/25 | 24/25 |
| Tiempo de inferencia (1821,2 s de audio) | 2333,6 s, unos 1,28 s por segundo de audio | 79,1 s, unas 23 veces más rápido que el tiempo real |
| WAV mono y RTTM | coinciden con el manifiesto | coinciden con el manifiesto |

Las métricas coinciden con 2 decimales. Las hipótesis de GPU no se compararon grabación por grabación porque no están en el repositorio.

**Inferencia CUDA sobre un WAV de 30 s, medición manual de la compañera:**
- 2 hablantes, 13 segmentos y 0 violaciones del contrato;
- pico de memoria asignada de 1628,5 MiB;
- **incremento residual de 8,12 MiB** después de `diarizar()`, por debajo del límite de 64 MiB.

También informó dos advertencias no bloqueantes: TF32 y `std(): degrees of freedom is <= 0`, que también aparece en CPU.

**Qué falta:**
- **7.3:** escribir `tests/test_evaluacion_gpu.py` (marker `gpu`). Debe medir la memoria de CUDA de forma **automatizada** (la medición de arriba fue manual), comprobar `dispositivo: "cuda"` y la compatibilidad funcional CPU/GPU sobre la primera grabación válida, y escribir `tests/reportes/gpu_S26.json`.
- **7.4:** en el equipo con GPU, falta:
  1. correr el nivel 1;
  2. correr `-m gpu`, una vez que exista la 7.3;
  3. confirmar si la instalación siguió solo esta guía, lo que serviría también para la 6.9;
  4. registrar qué FFmpeg se usó en Linux.

En el nivel 3a, `device="auto"` elige CUDA sin cambiar el código. Como la reutilización exige el mismo dispositivo, en GPU se diariza de nuevo.

La **tarea 7.5** (que la Etapa 4 consuma `diarization.json` sin transformaciones) queda pendiente de revisión y validación con el equipo.

### Estado de la tarea 6.9

La tarea pide un README completo, verificado **desde un entorno nuevo** hasta pasar el nivel 1, el nivel 2 y `--verificar`. Hoy está así:

| Requisito | Estado |
|---|---|
| FFmpeg 7.1.1 *shared* y `.pth` con `os.add_dll_directory`, 7-Zip, las dos variantes de PyTorch, token propio | documentado |
| Uso de la CLI y de la función, contrato, meta, archivo de error y contrato para el orquestador | documentado |
| Tolerancias (0,05 s de la salida, 0,01 s de la referencia) y preparación del dataset | documentado |
| Tabla de qué corre con y sin GPU | documentada |
| `verificar_entorno.py` con el entorno actual | verificado el 08/11/2026: 0 fallas, 0 avisos |
| Nivel 1 con el entorno actual | verificado: todas las pruebas pasan |
| Nivel 2 con el entorno actual | verificado el 08/11/2026: 6 pruebas pasan, y los `diarization.json` coinciden byte a byte con los de la tarea 5.3 |
| `--verificar` con el entorno actual | verificado: 25 grabaciones, `contenido_sha256` coincide |
| **Instalación desde cero siguiendo solo este README** (crear el `.venv`, instalar PyTorch y `requirements.txt` con `constraints.txt`, FFmpeg y el `.env`) y repetir esas cuatro verificaciones | **falta**: hay que reinstalar todas las dependencias, lo que descarga PyTorch y el modelo. Lo ideal es que lo haga otro integrante en su máquina, siguiendo la guía al pie de la letra y anotando cualquier paso que falte. La compañera que probó en GPU instaló un entorno cu128 en Ubuntu, pero no consta que haya seguido solo esta guía ni que haya corrido los niveles 1 y 2 |

La 6.9 se marca completa recién cuando se cumpla la última fila.

## Archivos

| Archivo | Qué hace |
|---|---|
| `diarizar.py` | CLI y función `diarizar(...)`; único que importa PyTorch y pyannote (dentro de las funciones) |
| `contrato.py` | validador del contrato y del par JSON/meta |
| `entrada.py` | cabecera del WAV (`wave`), `num_speakers`, token |
| `dispositivo.py` | selección `auto` / `cpu` / `cuda` |
| `segmentos.py` | normalización y acotado de los tiempos |
| `resultados.py` | carpeta de la reunión, escritura del par, registro del error |
| `errores.py` | `DiarizacionError` con la etapa del fallo |
| `requirements.txt` · `constraints.txt` | dependencias directas, exactas y sin PyTorch · *lock* de las 98 versiones verificadas (no instala nada) |
| `verificar_entorno.py` | comprobación del entorno: versiones, importaciones, CPU/GPU, FFmpeg, decodificación y token |
| `../../.env.example` | plantilla del `.env` con el token personal de Hugging Face (sin valores reales) |
| `evaluacion/` | dataset de Figshare (`rar7z.py`, `preparar_figshare.py`, `referencia.py`, `politica_etiquetas.json`, `figshare_test.manifest.json`) y, en el grupo 7, las métricas (`der.py`) |
| `datos/` | derivados locales, ignorados por git (`datos/figshare_test/S26/`) |
| `openspec/` | especificaciones de la Etapa 2 (OpenSpec): `changes/etapa-2-diarizacion/` con propuesta, diseño, specs, tareas y registro de pruebas. Se usa desde esta carpeta (ver "Especificaciones") |

## Especificaciones (OpenSpec)

Las especificaciones de esta etapa están en `PoC/paso2_diarizacion/openspec/`, separadas de las de otras etapas. El CLI de OpenSpec busca la carpeta `openspec/` más cercana subiendo desde la carpeta actual, así que hay que ejecutarlo **desde el módulo**:

```powershell
cd PoC/paso2_diarizacion
openspec list                                       # etapa-2-diarizacion y su avance
openspec validate etapa-2-diarizacion --strict
openspec instructions apply --change etapa-2-diarizacion --json
```

Si otra etapa adopta OpenSpec, puede crear su propio `PoC/<su-paso>/openspec/` con `openspec init` desde su carpeta, sin interferir con esta.
