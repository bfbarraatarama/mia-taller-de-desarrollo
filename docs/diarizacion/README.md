# Diarización de hablantes

Recibe el `audio.wav` normalizado por ingesta (16 kHz, mono, PCM16) y escribe `diarization.json`: quién habla y cuándo, con el modelo [`pyannote/speaker-diarization-community-1`](https://huggingface.co/pyannote/speaker-diarization-community-1). Admite CPU y GPU CUDA; el dispositivo se elige al ejecutarse. No se supone igualdad de resultados ni de rendimiento.

El modelo y su selección original se fundamentan en la [definición de la PoC](../../hito-3/definicion-de-la-poc.md#311-el-modelo). Las mediciones del desarrollo inicial y el estado de sus tareas se conservan en el [registro de desarrollo](../../evaluacion/diarizacion/registro-desarrollo.md). La ejecución integrada actual se documenta en [validación de integración](../validacion-integracion.md).

## Preparación del entorno

Todo desde la **raíz del repo**. La PoC integrada utiliza **un único `.venv` compartido**
por interfaz, diarización, STT, asociación y minutas. El instalador canónico y las
restricciones generales se describen en el `README.md` raíz; los procedimientos
de evaluación son específicos de la etapa.

### Requisitos del sistema

Utilizar las dependencias del sistema del [README raíz](../../README.md#entorno-único-para-todo-el-repositorio). El apartado de FFmpeg de esta guía conserva el procedimiento específico de las bibliotecas compartidas de FFmpeg.

### Entorno general

Seguir el [README raíz](../../README.md#entorno-único-para-todo-el-repositorio) y elegir el perfil CPU o cu128. En los comandos siguientes, `$py` representa su intérprete (en PowerShell se antepone `&`).

```powershell
$py = ".venv/Scripts/python.exe"
```

```bash
py=.venv/bin/python
```

### FFmpeg 7.1.1 *shared*, sin modificar el PATH del sistema

pyannote 4 lee el audio con TorchCodec, que carga las **bibliotecas compartidas** de FFmpeg (no `ffmpeg.exe`). TorchCodec 0.7 solo acepta FFmpeg **4 a 7**: con una 8 o una 9 falla con `Could not find module '...libtorchcodec_core7.dll' (or one of its dependencies)`. Si en el sistema ya hay otra FFmpeg, no hace falta desinstalarla: la consola la sigue usando.

#### Windows (procedimiento verificado durante el desarrollo del módulo)

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
   Set-Content -Encoding ascii .venv/Lib/site-packages/ffmpeg_dll_dir.pth $linea
   ```

   La ruta se calcula al inicio del intérprete, de modo que el archivo no necesita un nombre de usuario fijo. Se escribe en ASCII; la línea debe comenzar con `import`.

   - Afecta **solo a este venv**: no cambia el `PATH` de Windows ni otras instalaciones de Python.
   - Para usar otra carpeta, se define `DIARIZACION_FFMPEG_DLL_DIR` en el entorno de la consola antes de ejecutar. Ponerla en `.env` no sirve, porque el `.pth` corre antes de que se lea.
   - Para deshacerlo, se borra `ffmpeg_dll_dir.pth`. Si se recrea el venv, hay que repetir este paso.

#### Linux

> Una compañera pasó `verificar_entorno.py` sin fallas en Ubuntu 24.04, lo que incluye la decodificación con TorchCodec, y corrió la evaluación en CUDA. No informó cuál de las dos opciones de FFmpeg de abajo usó.

TorchCodec carga `libavcodec.so.61` y las demás con el cargador del sistema.

1. Mirar `ffmpeg -version`. Si la FFmpeg de la distribución es de la serie **4 a 7** (por ejemplo, la 6.1 de Ubuntu 24.04), alcanza con ella: `sudo apt install ffmpeg` o `sudo dnf install ffmpeg`.
2. Si es 8 o más nueva, se puede usar una build *shared* 7.1 local (por ejemplo, `ffmpeg-n7.1-latest-linux64-gpl-shared-7.1.tar.xz` de [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases)) extraída en `~/.local/ffmpeg7`. Se expone **solo en la consola en la que se ejecuta**, con `export LD_LIBRARY_PATH="$HOME/.local/ffmpeg7/lib:$LD_LIBRARY_PATH"`, sin tocar la configuración del sistema.

La verificación del entorno confirma que TorchCodec puede decodificar audio.

### Token personal de Hugging Face

1. Con tu cuenta, aceptá las condiciones de https://huggingface.co/pyannote/speaker-diarization-community-1.
2. Creá un token de tipo "Read" en https://huggingface.co/settings/tokens.
3. Si aún no existe `.env`, copiá la plantilla de la raíz y completá **tu** token:

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   # Linux: test -e .env || cp .env.example .env
   # editar .env:  HF_TOKEN=hf_...
   ```

`.env` está en `.gitignore` y nunca se versiona; `.env.example` no tiene ningún valor real. El módulo busca `.env` subiendo desde la carpeta en la que se ejecuta, así que hay que correr los comandos desde la raíz del repo. También sirven `HF_TOKEN` en el entorno, que tiene prioridad, o `hf auth login`. El token nunca se imprime ni se guarda en los resultados. Después de la primera descarga, el modelo queda en la caché de Hugging Face.

### Verificar el entorno

```powershell
& $py -m src.verificar_entorno                      # sin exigencia de CUDA
& $py -m src.verificar_entorno --gpu                # exige CUDA
& $py -m src.verificar_entorno --wav ruta\audio.wav # además, decodificar un WAV real
& $py -m pytest tests/diarizacion                                 # pruebas de nivel 1
```

`verificar_entorno.py` imprime OK, AVISO o FALLA por cada punto y termina con `0` si no hay fallas:

| Comprobación | Qué mira |
|---|---|
| Python | que sea 3.12.x |
| Versiones | dependencias directas y versiones instaladas frente a `constraints.txt` de la raíz; `pip check`; avisos por paquetes adicionales |
| Importaciones | `torch`, `torchaudio`, `torchcodec`, `pyannote.audio`, `pyannote.metrics`, `dotenv`, `numpy` y `pandas`, sin el aviso "torchcodec is not installed correctly" |
| CPU/GPU | variante del wheel (`+cpu`/`+cu128`), `torch.cuda.is_available()`, nombre de la GPU; con `--gpu`, falla si no hay CUDA |
| FFmpeg | la FFmpeg de la consola (informativo); en Windows, que exista `ffmpeg_dll_dir.pth` y que la carpeta tenga `avcodec-*.dll` |
| Decodificación | TorchCodec decodifica un WAV sintético (y el de `--wav`) y la cantidad de muestras coincide con la cabecera |
| Token | que haya `HF_TOKEN` en el entorno o en `.env`, sin mostrarlo |

> El verificador general del repositorio es `src.verificar_entorno`. En Linux se antepone `pw-jack` si se verifica JACK de PipeWire. Comprueba también las dependencias de captura, STT, asociación, minutas, datos y notebooks.

## Uso

Línea de comandos (desde la raíz del repo):

```powershell
& $py -m src.diarizacion.diarizar resultados/grabaciones/2026_11_07_10_00_00.wav
& $py -m src.diarizacion.diarizar audio.wav --device cpu --num-speakers 2 --salida resultados/reunion1
```

| Opción | Valor |
|---|---|
| `--device` | `auto` (por defecto: CUDA si está disponible, si no CPU), `cpu` (forzada), `cuda` (error si no hay CUDA; no pasa a CPU) |
| `--num-speakers` | opcional: cantidad exacta de hablantes. Sin ella, la estima pyannote. No cambia el contrato de salida |
| `--salida` | carpeta de resultados. Por defecto `<carpeta del audio>/<nombre del audio>/`, una por reunión |

Al terminar bien muestra cada etiqueta con su tiempo de habla, para revisarla a mano.

Como función:

```python
from src.diarizacion.diarizar import diarizar
from src.diarizacion.errores import DiarizacionError

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

- Un fallo recuperable, con restauración exitosa, conserva el `diarization.json` y el meta anteriores; un éxito posterior borra el `diarization.error.json`.
- **Publicación del par:** antes de reemplazarlo, el par vigente se copia a `*.bak`. Si falla la publicación de cualquiera de los dos archivos (disco lleno, permisos, archivo bloqueado), se intenta restaurar el par anterior, o borrar lo publicado si no había uno, y el error se registra con la etapa `escritura`. Si la restauración concluye, queda el par anterior intacto o ningún par.
- **Límite:** si el proceso se corta de golpe justo entre los dos reemplazos (corte de energía, proceso terminado a la fuerza), o si falla también la restauración, el par puede quedar inconsistente.
  - **Se detecta:** el `diarization_sha256` del meta no coincide con el JSON, así que el resultado no cuenta como vigente y `contrato.py --meta` lo informa.
  - **Cómo recuperarlo:** pueden quedar respaldos `*.bak`. Antes de restaurarlos manualmente, preservar los archivos y verificar que el par corresponda a la misma ejecución. En el flujo integrado se prefiere regenerar la etapa mediante el orquestador.
- Si el audio no existe o los parámetros son inválidos, no se crea nada.
- Etapas de error: `parametros`, `audio`, `token`, `dispositivo`, `modelo`, `decodificacion`, `ejecucion`, `contrato`, `escritura`.

### Normalización de los tiempos

Los tiempos se redondean a 3 decimales (véase [temporalidad](../temporalidad-transcripcion.md)) **sin superar nunca la duración real del WAV** (`D = nframes / 16000`). La regla es recortar al dominio representable y descartar únicamente intervalos no utilizables:

- **Se recorta** todo segmento con alguna parte dentro del audio, si conserva un intervalo no vacío: un `end` mayor que `D` pasa a `D3` (la duración truncada a 3 decimales, que nunca supera `D`) y un `start` negativo pasa a `0.0`. Cuenta como corregido.
- **Se descarta** solo lo que no tiene ninguna parte dentro del audio (`start >= D` o `end <= 0`) o queda vacío (`start >= end`) tras redondear y recortar, además de los tiempos no finitos.

| Campo del meta | Qué registra |
|---|---|
| `segmentos_corregidos` | segmentos recortados que se escribieron |
| `segmentos_descartados` | segmentos que no se escribieron |
| `exceso_fin_max_s` | el mayor exceso recortado por el final (`end - D`); 0,0 si no hubo ninguno |
| `tolerancia_fin_s` | **campo heredado** (0,05 s), que se conserva por compatibilidad. **Ya no controla los descartes**: solo sirve de referencia para leer `exceso_fin_max_s` (un exceso mayor indica un recorte por encima del redondeo habitual de frames) |

**Por qué recortar.** pyannote puede extender el último segmento algunas centésimas más allá del final del archivo, por la resolución de sus ventanas de análisis. Antes del 08/11/2026, todo exceso mayor a 0,05 s se descartaba. En una grabación interrumpida de 32,5 s, eso borró un tramo de habla real de 6 s, que pyannote había devuelto como 26,59–32,60 s. Ahora ese tramo se escribe como 26,592–32,5 s. El contrato de `diarization.json` no cambió.

Esto no afecta a la tolerancia de 0,01 s del Hito 2, que es de las anotaciones de referencia de Figshare.

## Validador del contrato

Solo usa la biblioteca estándar y no requiere cargar el modelo.

```powershell
python -m src.diarizacion.contrato diarization.json audio.wav
python -m src.diarizacion.contrato diarization.json audio.wav --meta diarization.meta.json
```

Informa cada violación con su ubicación (`segments[3]: end=... supera la duración...`) y termina con `0` si no hay ninguna o `1` si las hay. Con `--meta` comprueba además que el JSON y el meta son de la misma ejecución.

## Pruebas

```powershell
& $py -m pytest tests/diarizacion            # nivel 1: sin modelo ni GPU, en cualquier máquina
& $py -m pytest tests/diarizacion -m "slow or gpu" -rs   # qué falta para los niveles 2 y 3
& $py -m pytest tests/diarizacion -k integracion         # bloque A con archivos sintéticos (nivel 1)
```

| Nivel | Marker | Dónde corre |
|---|---|---|
| 1. Unitarias (contrato, normalización, entrada, token, dispositivo, resultados, errores, CLI, bloque A sintético) | ninguno | cualquier máquina, también sin GPU |
| 2. Integración Etapa 1 → Etapa 2 en CPU | `slow` | CPU (grupo 5). Requiere `$env:DIARIZACION_AUDIOS_CPU = (Resolve-Path resultados/grabaciones/nivel2).Path` |
| 3a. Calidad con Figshare (DER, JER, cantidad de hablantes) | `calidad` | **CPU o GPU**. Requiere el dataset preparado según la guía de evaluación; si falta, se omite con el motivo |
| 3b. Pruebas propias de CUDA (memoria, `dispositivo: cuda`, compatibilidad CPU/GPU) | `gpu` (pendiente, tarea 7.3) | equipo con GPU NVIDIA (otro integrante) |

Los procedimientos de preparación y evaluación con Figshare, tolerancias de referencia y resultados publicados se encuentran en [evaluación de diarización](../../evaluacion/diarizacion/README.md).

## Archivos

| Archivo | Qué hace |
|---|---|
| `src/diarizacion/diarizar.py` | CLI y función `diarizar(...)`; único que importa PyTorch y pyannote (dentro de las funciones) |
| `src/diarizacion/contrato.py` | validador del contrato y del par JSON/meta |
| `src/diarizacion/entrada.py` | cabecera del WAV (`wave`), `num_speakers`, token |
| `src/diarizacion/dispositivo.py` | selección `auto` / `cpu` / `cuda` |
| `src/diarizacion/segmentos.py` | normalización y acotado de los tiempos |
| `src/diarizacion/resultados.py` | carpeta de la reunión, escritura del par, registro del error |
| `src/diarizacion/errores.py` | `DiarizacionError` con la etapa del fallo |
| `src/verificar_entorno.py` | comprobación del entorno: versiones, importaciones, CPU/GPU, FFmpeg, decodificación y token |
| `.env.example` | plantilla del `.env` con el token personal de Hugging Face (sin valores reales) |
| `evaluacion/diarizacion/` | dataset de Figshare (`src/rar7z.py`, `preparar_figshare.py`, `referencia.py`, `politica_etiquetas.json`, `figshare_test.manifest.json`) y, en el grupo 7, las métricas (`der.py`) |
| `evaluacion/diarizacion/datos/` | derivados locales, ignorados por git (`evaluacion/diarizacion/datos/figshare_test/S26/`) |
| `docs/diarizacion/openspec/` | especificaciones de la Etapa 2 (OpenSpec): `changes/etapa-2-diarizacion/` con propuesta, diseño, specs, tareas y registro de pruebas. Se usa desde `docs/diarizacion/` (ver "Especificaciones") |

## Especificaciones (OpenSpec)

Las especificaciones de esta etapa están en `docs/diarizacion/openspec/`, separadas de las de otras etapas. El CLI de OpenSpec busca la carpeta `openspec/` más cercana subiendo desde la carpeta actual, así que hay que ejecutarlo **desde `docs/diarizacion/`**:

```powershell
cd docs/diarizacion
openspec list                                       # etapa-2-diarizacion y su avance
openspec validate etapa-2-diarizacion --strict
openspec instructions apply --change etapa-2-diarizacion --json
```

Si otra etapa adopta OpenSpec, puede crear su propio `docs/<componente>/openspec/` con `openspec init` desde su carpeta, sin interferir con esta.
