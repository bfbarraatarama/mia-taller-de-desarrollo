# Design

## Context

Ver [proposal.md](proposal.md) para la motivación. Los requisitos están en [specs/diarizacion-hablantes/spec.md](specs/diarizacion-hablantes/spec.md), para el módulo, y en [specs/evaluacion-diarizacion/spec.md](specs/evaluacion-diarizacion/spec.md), para el dataset de test y el DER.

Estado actual:

- **Paso 1.** `PoC/paso1_captura/` produce WAV de 16 kHz, mono y PCM16, y los guarda todos en una misma carpeta con el nombre `AAAA_MM_DD_HH_MM_SS.wav`. Su panel espera un orquestador `PoC/paso2_procesamiento/procesar.py` que todavía no existe y que **no** forma parte de este change.
- **`.gitignore`.** Ignora `PoC/*` salvo `paso1_captura/`, así que hay que agregar `PoC/paso2_diarizacion/` como excepción. También ignora `hito-2/.cache/` y `hito-2/muestra/uba_games_figshare/` (derivados con redistribución pendiente).
- **Entorno.** El de las etapas 2 y 3 es compartido (PyTorch, unos 3 GB) y usa Python 3.12; el `.venv` de la raíz es el de la interfaz. La máquina de desarrollo (Windows 11, sin GPU) tiene Python 3.12, pero no tiene PyTorch ni la caché de Figshare. Las máquinas de referencia tienen una RTX 3050 de 6 GB, que Whisper `medium` usa **después** de la diarización.
- **Token.** El de la responsable está en `.env` en la raíz, ignorado por git. Cada integrante usa el suyo.
- **Figshare v2 en el Hito 2.**
  - **Originales:** dos RAR en `hito-2/.cache/uba_games/figshare-v2/`. `phrases.rar` trae las anotaciones (347 152 bytes) y `wavs.rar` los audios (721 854 279 bytes), registrados en `fuentes.toml` (MD5) y `fuentes.lock.json` (SHA-256).
  - **Nombres internos:** `sN.objects.TT.channelC.{phrases|wav}`. Una tarea es una grabación con dos canales, uno por participante. En S26 hay además un WAV estéreo completo por tarea, en "Sin separar canales/S26_falta_separar_canales/", que es la entrada elegida para el nivel 3 (§11). Los archivos ya están extraídos en `hito-2/.cache/uba_games/figshare-v2/extraidos/`.
  - **Anotaciones:** líneas `inicio<TAB>fin<TAB>texto`. `#` es silencio marcado: `normalizar_muestra.py` lo guarda con `scored_as_speech=False` y sin hablante. El Hito 2 no definió cómo puntuar el resto ("no generar RTTM sin decidir política de puntuación").
  - **Criterios ya establecidos:** ambos canales con audio y anotación, 16 kHz, mono, PCM16, lectura completa del WAV, alineación de una muestra o menos, tolerancia de fin `TOLERANCIA_FIN_FIGSHARE_S = 0.01` (`validar_muestra.py`), orden con tolerancia de 1e-4 y mezcla `(canal1 + canal2) // 2`.
  - **Lectura de RAR:** el Hito 2 usa libarchive por `ctypes`, que en Windows no está disponible de forma práctica.

## Goals / Non-Goals

**Goals:**
- Un único código que corre en CPU y en GPU, eligiendo el dispositivo al ejecutarse.
- Que la validación, el dispositivo, la normalización, el contrato, el manejo de errores y la preparación del dataset se prueben sin el modelo y sin los originales.
- Que un fallo nunca se confunda con un éxito ni destruya el último resultado válido.
- Un dataset de test que cualquier integrante pueda regenerar con los mismos SHA-256, en Windows o en Linux.

**Non-Goals:**
- Reintentar, detener el flujo o elegir qué resultado usar: le corresponde al orquestador.
- Emitir eventos de avance para la interfaz.
- Pasar automáticamente a CPU si la GPU falla.
- Normalizar audio de la Etapa 1.
- Fijar umbrales de DER y JER, usar las otras seis sesiones de Figshare o CALLHOME.
- Modificar los scripts o los originales del Hito 2.

## Decisions

### 1. Estructura del módulo

```
PoC/paso2_diarizacion/
  diarizar.py          CLI + función diarizar(...); único que importa torch/pyannote
  contrato.py          validar_diarizacion, validar_par; solo stdlib
  entrada.py           validar_audio (wave), obtener_token
  dispositivo.py       elegir_dispositivo(modo)
  segmentos.py         normalizar(turnos, duracion)
  resultados.py        carpeta de la reunión, escritura del par, registro del error
  requirements.txt     dependencias salvo PyTorch
  README.md
  evaluacion/
    preparar_figshare.py         prepara y verifica el dataset de test (sin torch)
    rar7z.py                     listado y extracción con 7-Zip
    referencia.py                anotaciones -> referencia RTTM; validación
    der.py                       DER por grabación y sesión (pyannote.metrics)
    politica_etiquetas.json      clasificación de etiquetas especiales   [versionado]
    figshare_test.manifest.json  procedencia y SHA-256                    [versionado]
  datos/figshare_test/           mezclas .wav y referencias .rttm         [ignorado]
  tests/                         niveles 1, 2 y 3; tests/reportes/        [ignorado]
```

- **`paso2_diarizacion` como hermana de `paso1_captura`.** Deja `paso2_procesamiento/` libre para el orquestador, que va a importar `diarizar(...)` o lanzar la CLI.
- **Solo `diarizar.py` y `evaluacion/der.py` importan torch o pyannote, y lo hacen dentro de sus funciones.** La preparación del dataset no necesita PyTorch ni GPU, así que corre en la máquina de desarrollo.
- **`.gitignore`** suma `!PoC/paso2_diarizacion/`, `PoC/paso2_diarizacion/datos/` y `PoC/paso2_diarizacion/tests/reportes/`.

### 2. Lectura del audio en la Etapa 2: cabecera con `wave`, decodificación con FFmpeg

- **Supuesto 1, resuelto:** `entrada.validar_audio` lee solo la cabecera con `wave` (frecuencia, canales, `sampwidth == 2`, PCM) y calcula la duración como `nframes / framerate`. No decodifica ni suma dependencias, igual que el Hito 2 con `wave`.
- **Decodificación:** pyannote recibe la **ruta** del WAV y lo decodifica con `torchcodec`, que usa FFmpeg. Un fallo de importación o de decodificación se informa como "FFmpeg no disponible o incompatible".
- **Supuesto 2, resuelto:** FFmpeg es una **dependencia del sistema que comparten las etapas 1 a 3**. No se instala con pip. `torchcodec` carga las **bibliotecas compartidas** de FFmpeg, no `ffmpeg.exe`, así que hace falta una build *shared*. Con `torchcodec 0.7` (la serie de torch 2.8) solo sirven las versiones **4 a 7**; la versión verificada es **FFmpeg 7.1.1 *shared*** (§8).
  - **Windows:** poner la carpeta `bin` en `PATH` **no funciona**: desde Python 3.8, las DLL de las que depende una extensión no se buscan en `PATH`. Se registra con `os.add_dll_directory` desde un `ffmpeg_dll_dir.pth` en `site-packages` del venv. Así no se modifica el `PATH` del sistema y puede convivir otra FFmpeg (por ejemplo, la 9.x de la consola).
  - **Linux:** la FFmpeg de la distribución, si es de la serie 4 a 7, o una build *shared* 7.1 expuesta con `LD_LIBRARY_PATH` solo en la sesión. Está **pendiente de verificar** en las máquinas con GPU.
- **Verificación:** `verificar_entorno.py` comprueba las versiones contra `constraints.txt`, las importaciones (sin el aviso de torchcodec), CPU/GPU, la carpeta de DLL en Windows y que TorchCodec decodifique un WAV completo (sintético y, con `--wav`, uno real). La prueba de nivel 2 lo confirma con grabaciones de la interfaz.
- **Por qué no `soundfile`:** lo decidió el equipo. Si FFmpeg resulta inviable en Windows, se vuelve a discutir **antes** de cambiar.

### 3. Flujo de una ejecución

```
validar num_speakers --> resolver carpeta --> validar audio --> token --> dispositivo
  (y que el audio exista)   de la reunión     (wave)
   | error: código != 0, stderr; no se crea nada
   v                                  | error: diarization.error.json, código != 0
                                      v
          cargar pipeline --> .to(device) --> ejecutar(ruta, num_speakers)
                 |                                    |
                 | finally: del out, del pipeline;    v
                 | gc.collect();             normalizar segmentos (sección 4)
                 | si cuda: empty_cache()             |
                 v                                    v
     error: diarization.error.json        validar contrato --> escribir el par (sección 5)
            resultado anterior intacto                          borrar diarization.error.json
```

`run_id` es la fecha y hora de inicio más 6 caracteres aleatorios. Se usa `out.speaker_diarization`, que conserva el solapamiento.

### 4. Normalización de los segmentos de la Etapa 2

**Regla: recortar y no descartar.** Un segmento que tiene alguna parte dentro del audio se recorta a los límites del WAV, sea cual sea su exceso. Solo se descartan los que no tienen ninguna parte dentro del audio, o los que quedan vacíos al redondear.

> **Por qué cambió (08/11/2026).** La regla anterior descartaba entero todo segmento cuyo `end` superara la duración en más de 0,05 s (`TOLERANCIA_FIN_S`). En la grabación interrumpida `2026_11_08_11_41_26.wav` (32,5 s), pyannote devolvió el último tramo de habla como 26,5922–32,5997 s: 6,0 s de voz real que terminaban 0,0997 s después del final, por la resolución de sus ventanas de análisis. La regla lo descartó y `diarization.json` perdió esos 6 s (ver [registro-pruebas.md](registro-pruebas.md)). Afecta a toda grabación que termina mientras alguien habla, que es justo el caso de una interrupción. El exceso de un segmento que empieza dentro del audio es un artefacto de la resolución del modelo, no habla fuera del archivo: recortarlo conserva la habla real y nunca deja tiempos fuera del WAV.

El orden importa: **primero se decide y después se redondea**, y el redondeo nunca puede sacar un tiempo del audio. `D` es la duración real, `nframes / framerate` de la cabecera, sin redondear.

1. **Decisión con tiempos crudos contra `D`**, sin tolerancia:
   - Si `start_crudo >= D` o `end_crudo <= 0`, el segmento no tiene ninguna parte dentro del audio y **se descarta**.
   - Si no, y además `end_crudo > D` o `start_crudo < 0`, **se marca como corregido** y se recorta en los pasos siguientes.
   - Se guarda `exceso_fin_max_s`: el mayor `end_crudo - D` entre los segmentos corregidos por el final, o 0,0 si no hubo ninguno. Sirve para ver en el meta cuánto se recortó.
2. **Techo de 3 decimales:** `D3 = floor(D * 1000) / 1000`. Si por la representación binaria quedara `D3 > D`, se resta 0,001. Así se garantiza `D3 <= D`.
3. **Redondeo acotado:** `start = min(max(round(start_crudo, 3), 0.0), D3)` y `end = min(max(round(end_crudo, 3), 0.0), D3)`. Después, `start + 0.0` y `end + 0.0` convierten un posible `-0.0` en `0.0`.
4. Si queda `start >= end` (por ejemplo, un segmento de menos de 0,5 ms o uno que empieza en los últimos milisegundos), se descarta. Un segmento descartado acá no cuenta también como corregido.
5. Se ordena por `(start, end, speaker)` y se vuelve a validar el contrato contra `D`. Una violación restante es un bug: la ejecución falla en la etapa `contrato`.

**Campos del meta sobre la normalización:**

| Campo | Qué registra |
|---|---|
| `segmentos_corregidos` | segmentos recortados a los límites del WAV que se escriben |
| `segmentos_descartados` | segmentos que no se escriben (fuera del audio o vacíos tras redondear) |
| `exceso_fin_max_s` | **nuevo:** el mayor `end_crudo - D` entre los segmentos recortados por el final; 0,0 si no hubo ninguno |
| `tolerancia_fin_s` | **heredado, se conserva por compatibilidad** con los metas ya generados. Sigue valiendo 0,05 (`TOLERANCIA_FIN_S`), pero **ya no controla los descartes ni las correcciones**. Solo es una referencia para leer `exceso_fin_max_s`: un valor por encima de 0,05 s indica un recorte mayor que el redondeo habitual de frames del modelo |

El **contrato de `diarization.json` no cambia**: siguen siendo solo `segments` con `start`, `end` y `speaker`, en `[0, D]` y ordenados. Los campos del meta se agregan o se conservan: no se quita ninguno.

Como `D3 <= D` y todo tiempo queda en `[0, D3]`, ningún segmento escrito puede quedar fuera de la duración real del WAV, aunque el redondeo empuje hacia arriba. Los floats que salen de `round` se serializan con `repr`, que en Python es determinista y se lee de vuelta con el mismo valor. Los solapamientos entre hablantes no se tocan.

La misma función de acotado (pasos 2 a 4) la usa `evaluacion/referencia.py` para escribir los tiempos del RTTM, así la referencia tampoco supera la duración real de la mezcla.

**Casos límite con test (tarea 2.3):**
- **Regresión del caso real:** `D = 520000 / 16000 = 32,5 s` y el segmento crudo 26,5922–32,5997 s dan `{"start": 26.592, "end": 32.5}`, con 1 corregido, 0 descartados y `exceso_fin_max_s ≈ 0,0997`. Se reproduce también con los 8 turnos crudos completos de esa grabación: los 8 se escriben, el último recortado.
- `D` con más de 3 decimales (`197531 / 16000 = 12,3456875 s`) y `end_crudo == D`: da `end = 12.345`, sin corrección.
- `end_crudo = D + 0.0004`: se corrige y queda en `12.345`.
- `end_crudo = D + 0.5` con `start_crudo` dentro del audio: se corrige y queda en `D3` (antes se descartaba).
- `start_crudo = D` o mayor: se descarta (fuera del audio). `end_crudo <= 0`: se descarta.
- `start_crudo = 12.3455` y `end_crudo = 12.3456`: se descarta, porque queda vacío tras redondear y recortar.
- `start_crudo = -0.3` y `end_crudo = 1.0`: queda `start = 0.0`, corregido (antes se descartaba).
- `start_crudo = -0.0004`: da `0.0`, no `-0.0`.
- Segmento de 0,0004 s en medio del audio: se descarta.
- Audio de menos de 1 ms: `D3 = 0`, todo se descarta y la salida es `segments: []`, válida.
- Una propiedad sobre miles de segmentos aleatorios y duraciones aleatorias en cuadros de 16 kHz: todo segmento escrito cumple `0 <= start < end <= D`. Además, **ningún segmento con parte dentro del audio se pierde salvo que quede vacío al redondear**: `escritos + descartados == total`, y cada descartado está fuera de `[0, D)` o mide menos de 1 ms tras recortar.

**Esto no cambia la tolerancia de 0,01 s del Hito 2**, que se aplica a las anotaciones de referencia de Figshare (sección 11) y es independiente de la salida del modelo.

### 5. Archivos de resultados y consistencia

Carpeta de la reunión: por defecto `<carpeta del audio>/<nombre del audio sin extensión>/`, o `--salida`.

| Archivo | Cuándo | Contenido |
|---|---|---|
| `diarization.json` | Solo en un éxito | Contrato exacto |
| `diarization.meta.json` | Solo en un éxito, después del JSON | `run_id`, audio (ruta, duración, `sha256`), `modo_dispositivo`, `dispositivo`, `gpu`, modelo, versiones, `num_speakers`, `tolerancia_fin_s` (heredado, sin efecto en los descartes), `exceso_fin_max_s`, `hablantes`, `segmentos`, `segmentos_corregidos`, `segmentos_descartados`, `tiempo_s`, `inicio`, `diarization_sha256` y, en GPU, `vram_pico_mib` |
| `diarization.error.json` | Solo en un fallo | `run_id`, `inicio`, `etapa`, `tipo`, `mensaje`, `modo_dispositivo`, `resultado_anterior_conservado`, `run_id_anterior` |

Escritura del par:

1. Se serializa el JSON y se calcula su SHA-256.
2. Se escriben los dos `.tmp`.
3. `os.replace` del JSON y después del meta.
4. Se borra `diarization.error.json`.

Si el proceso muere entre los dos `os.replace`, `validar_par` detecta el par inconsistente.

**Supuesto 5, resuelto:** una ejecución exitosa borra el `diarization.error.json` de un intento anterior. Así, en la carpeta, un resultado vigente nunca convive con un error que ya no lo describe. El error anterior no se archiva: la evidencia de un fallo es el código de salida y la excepción del momento.

El orquestador decide por el código de salida (`0` éxito, `2` parámetros, `1` otro fallo) o por `DiarizacionError`, nunca por la existencia de `diarization.json`.

### 6. Selección del dispositivo

`elegir_dispositivo(modo)` consulta `torch.cuda.is_available()` y se prueba simulándolo. Con `cuda` sin GPU, lanza `DiarizacionError` (etapa `dispositivo`). **Descartado:** pasar a CPU en `auto` si CUDA falla, porque escondería un wheel mal instalado y falsearía la latencia.

### 7. Liberación de la GPU

En el `finally`:

1. `del out`.
2. `del pipeline`.
3. `gc.collect()`.
4. `torch.cuda.empty_cache()`, solo en `cuda`.

Antes de liberar se registra `torch.cuda.max_memory_allocated()` como `vram_pico_mib`. La función devuelve un `dict` sin tensores. El criterio es `memory_allocated()` antes y después de la llamada, con un margen de 64 MiB; no se exige que la memoria del sistema quede en cero.

### 8. Instalación: mismo código, dos wheels

`requirements.txt` no incluye `torch` ni `torchaudio`. Primero se instala uno de estos dos:

```
CPU:  pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
GPU:  pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
```

Después, el resto **con restricciones**:

```
pip install -r PoC/paso2_diarizacion/requirements.txt -c PoC/paso2_diarizacion/constraints.txt
```

Por último, `pip check` y `verificar_entorno.py` (§2).

**`requirements.txt`** fija **exactas** las dependencias directas, sin PyTorch: `pyannote.audio==4.0.7`, `pyannote.metrics==4.2.0`, `torchcodec==0.7.0`, `python-dotenv==1.2.4` y `pytest==9.2.0`.

**`constraints.txt`** (versionado junto a `requirements.txt`) es el *lock* del árbol verificado: **98 paquetes con versión exacta**. Las líneas clave:

```
torch==2.8.0
torchaudio==2.8.0
torchcodec==0.7.0
pyannote.audio==4.0.7
pytorch-metric-learning==2.9.0
```

- No incluye `pip` ni `setuptools`, ni los paquetes de CUDA (`nvidia-*`, `triton`), que fija el propio wheel cu128.
- `colorama` solo se instala en Windows; en Linux su línea no tiene efecto.
- Se regenera solo si el equipo acuerda cambiar versiones.
- `verificar_entorno.py` compara cada paquete instalado con el lock y avisa si hay paquetes fuera de él. Un test de nivel 1 comprueba que `requirements.txt` y `constraints.txt` coinciden y que no tienen etiquetas `+cpu`/`+cu`.

- **Por qué hace falta.** En la implementación se confirmó el riesgo de que pip reemplace el PyTorch elegido. `pytorch-metric-learning` 3.x, que es dependencia de `pyannote.audio` 4, exige `torch>=2.14`. Sin restricciones, pip instaló `torch 2.15.0` y `torchaudio 2.11.1` desde PyPI, junto con `torchcodec 0.17`, que está atado a esa versión de torch. Con `-c`, el resolver eligió `pytorch-metric-learning 2.9.0` y `torchcodec 0.7.0`, y conservó `torch 2.8.0+cpu`.
- **Qué hacen las restricciones.** No instalan nada: solo acotan versiones, así que PyTorch sigue fuera de `requirements.txt` y el wheel de cada máquina se elige con el `--index-url`. `==2.8.0` acepta tanto `2.8.0+cpu` como `2.8.0+cu128`, porque PEP 440 ignora la etiqueta local en `==`.
- **`torchcodec==0.7.0`.** Es la serie compatible con torch 2.8, y fija también qué FFmpeg sirve (sección 2): de la 4 a la 7.
- **Alternativa descartada:** poner `torch==2.8.0` en `requirements.txt`. En un entorno sin PyTorch previo, pip lo bajaría de PyPI con la variante por defecto de cada sistema, y no la que corresponde a cada máquina.

**Entorno verificado en la máquina de desarrollo (07/11/2026):** Windows 11, Python 3.12.10, `torch 2.8.0+cpu`, `torchaudio 2.8.0+cpu`, `torchcodec 0.7.0`, `pyannote.audio 4.0.7`, `pyannote.metrics 4.2.0`, `pytorch-metric-learning 2.9.0` y FFmpeg 7.1.1 *shared*. `pip check` no da conflictos y `verificar_entorno.py` no da fallas, también en un venv nuevo instalado siguiendo el README. Quedan pendientes la variante cu128 y Linux.

**FFmpeg para `torchcodec 0.7`:**
- **Problema:** solo carga FFmpeg **4 a 7**, y la 9.0.2 de la máquina de desarrollo no sirve.
- **Instalación:** se instaló localmente la build *shared* 7.1.1 de gyan.dev, desde su repositorio oficial en GitHub, en `%LOCALAPPDATA%\ffmpeg7\`. Fue sin administrador y sin tocar la 9.0.2.
  - Verificación: tamaño de 46 646 819 bytes y `7z t` correcto.
  - SHA-256 observado, porque gyan.dev no lo publica: `B73E7ED7…42780B3`.
- **Registro de las DLL:** en Windows **no alcanza con ponerla en `PATH`**, porque desde Python 3.8 las DLL dependientes de una extensión no se buscan ahí. Se registra con `os.add_dll_directory` mediante `ffmpeg_dll_dir.pth` en `site-packages` del venv.
  - Su única línea calcula la carpeta desde `LOCALAPPDATA` al ejecutarse, o toma `DIARIZACION_FFMPEG_DLL_DIR`. Así es igual para todos los usuarios.
  - El contenido es ASCII puro. Python 3.12 lee los `.pth` como `utf-8-sig`, así que un BOM no molesta (comprobado). La línea tiene que empezar con `import` para que se ejecute.
  - Vale solo para ese venv y se deshace borrando el archivo. El procedimiento está en el README.

Herramientas del sistema: FFmpeg (sección 2) y 7-Zip (sección 11).

### 9. Token

1. `HF_TOKEN` del entorno.
2. Si falta, `find_dotenv(usecwd=True)` sin sobrescribir.
3. El token se pasa a `from_pretrained` y nunca se imprime ni se serializa.
4. Sin token pero con el modelo en caché, se intenta cargar igual.

El README explica cómo crea cada integrante su propio token.

### 10. Pruebas en tres niveles

| Nivel | Marker | Máquina | Necesita | Qué comprueba |
|---|---|---|---|---|
| 1. Unitarias | ninguno | **la tuya (Windows sin GPU)** y todas | Python, `pytest`, 7-Zip para los RAR sintéticos (si falta, solo se saltean esos tests) | módulo: entrada, token, dispositivo, normalización, contrato, par, errores, CLI. Dataset: nombres, validez, mezcla, política de etiquetas, unión, ajuste de fin dentro de 0,01 s, validación de la referencia, manifiesto, verificación y las dos métricas de DER sobre casos armados a mano |
| 2. Integración Etapa 1 → Etapa 2 en CPU | `slow` | **la tuya** | entorno del paso 1 para grabar; torch CPU, FFmpeg y token; grabaciones de 30 a 60 s **hechas con la interfaz** en `DIARIZACION_AUDIOS_CPU` | contrato de salida de la Etapa 1 (cabecera y reporte), entrada aceptada por la Etapa 2, `diarization.json` con intervalos y `SPEAKER_NN`, archivos de la Etapa 1 intactos y revisión manual (sección 10.1). Es previa a Figshare y no la reemplaza |
| Preparación del dataset | (script) | **la tuya o cualquiera**, sin GPU | 7-Zip, los dos RAR, Python con NumPy | `preparar_figshare.py` y `--verificar` (sección 11) |
| 3a. Calidad con Figshare | `calidad` | **CPU o GPU** (incluida la máquina de desarrollo) | torch (CPU o cu128), token, FFmpeg 4–7, dataset preparado | verificación del dataset contra el manifiesto; cada grabación válida, en una corrida principal (sin `num_speakers`) y una diagnóstica (`num_speakers=2`): contrato al 100 % (A); DER estricto y con tolerancia, JER, componentes, cantidad de hablantes y dispersión (B); dispositivo y tiempo registrados (sección 12) |
| 3b. Pruebas propias de CUDA | `gpu` | **equipo con GPU NVIDIA** (otro integrante) | wheel cu128, CUDA, dataset preparado | `dispositivo == "cuda"`; memoria antes, después y pico; compatibilidad funcional CPU/GPU sobre un subconjunto, sin comparar precisión (sección 12) |

Cada nivel se saltea con un motivo legible cuando falta lo que necesita. Los reportes van a `tests/reportes/` (ignorado).

#### 10.1 Nivel 2: integración Etapa 1 → Etapa 2

```
 interfaz.py (paso 1, su propio entorno)          tests/test_integracion_cpu.py (entorno de la Etapa 2)
 +-------------------------------+                +------------------------------------------------+
 | grabar 30-60 s, 2 voces       |                | por cada <nombre>.wav con su <nombre>.json:   |
 |  -> grabaciones/<nombre>.wav  | ---- disco --> |  A. contrato de la Etapa 1                    |
 |  -> grabaciones/<nombre>.json |                |  B. diarizar(wav, device="cpu")               |
 +-------------------------------+                |  C. salida de la Etapa 2                       |
                                                  |  D. compatibilidad                            |
                                                  +------------------------------------------------+
```

Las dos etapas se comunican solo por el disco, como en la PoC. El test **no** importa código del paso 1, porque tienen entornos distintos (el paso 1 usa `soundfile`, PySide6 y Python 3.14 o 3.12). La grabación la hace una persona con la interfaz; el test consume lo que quedó en disco.

| Bloque | Qué comprueba | Cómo |
|---|---|---|
| A. Contrato de la Etapa 1 | El WAV es de 16 kHz, mono y PCM16, y no está vacío; su reporte existe, tiene `estado: "completa"` y la prueba "salida procesable" con `ok: true`; la duración está entre 30 y 60 s | `entrada.validar_audio` (cabecera con `wave`) y lectura del `.json` del paso 1. Si falta el reporte, el test falla: la grabación no salió de la interfaz |
| B. Recepción | La Etapa 2 acepta el WAV sin conversión, FFmpeg lo decodifica y pyannote corre en CPU | `diarizar(..., device="cpu")` termina sin excepción |
| C. Salida | `diarization.json` cumple el contrato al 100 % (intervalos con `0 <= start < end <= duración` y etiquetas `SPEAKER_NN`), con al menos 1 hablante y 1 segmento; el meta registra `cpu` y la misma duración que la cabecera; el par es consistente | `contrato.validar_diarizacion` y `validar_par` |
| D. Compatibilidad | El SHA-256 del WAV y del reporte del paso 1 no cambia; los resultados quedan en `grabaciones/<nombre>/` y no pisan `grabaciones/<nombre>.json`; dos grabaciones de la misma carpeta dan carpetas de resultados distintas | hashes antes y después y rutas |

- **Revisión manual.** El test escribe `tests/reportes/integracion_<nombre>.json` con la cantidad de hablantes, el tiempo de habla por etiqueta, los primeros 3 segmentos de cada una y `tiempo_s`. La persona que grabó lo compara con lo que se oye y lo anota en la tabla del README. La cantidad de hablantes **no** se exige automáticamente, porque depende del modelo: se registra.
- **Grabaciones.** Al menos tres:
  1. Dos voces con auriculares.
  2. Dos voces con parlantes, que registra el riesgo de eco.
  3. Una grabación cerrada a la fuerza durante la captura. Su reporte queda en "grabando", y el bloque A acepta ese estado. Como no hay un reporte final que avale el archivo, la cabecera sola no alcanza: el bloque A **verifica además que el WAV se decodifica completo**, como se explica abajo.

  **Decodificación completa** (en el bloque A, para las tres grabaciones; obligatoria para la interrumpida):
  1. Se leen todos los cuadros con `wave.readframes`, y los bytes leídos tienen que ser `nframes * 2`. Es el mismo criterio de "lectura completa" del Hito 2.
  2. Se decodifica con FFmpeg dentro del entorno (`torchcodec.decoders.AudioDecoder(...).get_all_samples()`), sin errores, y la cantidad de muestras tiene que ser igual a `nframes`.
  3. Se corre `ffmpeg -v error -i <wav> -f null -`, que no tiene que imprimir nada en stderr.

  Si falla cualquiera de los tres, el test falla e informa cuál, antes de diarizar.

  Ninguna se versiona: `PoC/paso1_captura/grabaciones/` ya está en `.gitignore`.
- **Fuentes en Windows.** El modo automático de la interfaz es solo para PipeWire (Linux). En Windows se usa el modo manual, con el micrófono y una fuente de audio del sistema (Stereo Mix, loopback o VB-Cable). Las dos voces pueden ser dos personas frente al micrófono, o una frente al micrófono y otra por una llamada o un video que suena por el sistema.

### 11. Preparación del dataset de test (S26, empezando por `s26.objects.04`)

> **Cambio de alcance (08/11/2026).** Reemplaza al dataset S21–S23 aprobado antes.
> - **Sesión S26.** La evaluación empieza por **una sola grabación**, `s26.objects.04` (52,271 s), para verificar el pipeline; después se amplía a las demás tareas de S26.
> - **Entrada:** el **WAV estéreo completo** de cada tarea, de `wavs/Sin separar canales/S26_falta_separar_canales/`, convertido a mono como hace la aplicación. Esto **invierte** la regla anterior, que excluía esa carpeta. Los WAV separados de `wavs/S26/` no se usan como entrada del modelo.
> - **Fuente:** se usan los archivos ya extraídos de `hito-2/.cache/uba_games/figshare-v2/extraidos/`, **verificados contra el listado del RAR** (tamaño y CRC32). No se extrae nada y no hace falta descargar.
> - **Verificación previa, de solo lectura:**
>   - en `s26.objects.04`, el canal izquierdo del WAV completo coincide con `channel1.wav` (correlación 0,99996, desfase 0) y el derecho con `channel2.wav` (0,99999, desfase 0);
>   - las dos anotaciones terminan 0,0092 s después del WAV;
>   - los RAR coinciden con `fuentes.lock.json`.
> - **Pendiente, sin implementar:** comparar con S21–S23, donde cada canal mono tiene una voz predominante y otra más lejana, para ver cómo responde pyannote ante diferencias de intensidad entre hablantes.

Una grabación es una tarea (`figshare_v2_S26_objects_<TT>`): un WAV estéreo con un hablante principal por canal, más las dos anotaciones `.channel1.phrases` y `.channel2.phrases`. Cada grabación se diariza por separado.

```
fuentes.toml + fuentes.lock.json
          |  verificar bytes, MD5 y SHA-256 de phrases.rar y wavs.rar  (falla: nada escrito)
          v
 7z l -slt -ba sobre los dos RAR  -->  inventario de entradas (ruta, tamaño, CRC32); rutas absolutas o con .. -> falla
          |
          v
 extraidos/ : por cada archivo seleccionado, tamaño y CRC32 == entrada del RAR  (falla: nada escrito)
          |   wavs/Sin separar canales/S26_falta_separar_canales/s26.objects.<TT>.wav
          |   phrases/S26/s26.objects.<TT>.channel1.phrases y .channel2.phrases
          v
 por tarea: validar WAV estéreo y anotaciones  --no-->  excluida + motivo
          | sí
          v
 mono (izquierda + derecha) // 2  -->  datos/figshare_test/S26/<grabacion>.wav
 referencia de 2 hablantes        -->  datos/figshare_test/S26/<grabacion>.rttm
 indicador de cobertura por canal (energía contra anotación; solo indicio)
          |
          v
 evaluacion/figshare_test.manifest.json  (procedencia, estado, CRC32, SHA-256 y cobertura por grabación)
```

**Selección:** la lista de tareas se fija en el manifiesto (`seleccion: ["04"]` al principio). Ampliarla a otras tareas de S26 es un cambio explícito de esa lista, que cambia `contenido` y requiere autorización.

**Reutilización del Hito 2 sin modificarlo:**
- `TOLERANCIA_FIN_FIGSHARE_S` se **importa** de `hito-2/scripts/validar_muestra.py`. Necesita NumPy y pandas, que ya trae `pyannote.metrics`.
- `armar_muestra.py` **no se importa**: carga `soundfile` y `lxml` al importarse. El patrón de nombres, la validación de líneas y la fórmula de mezcla se replican en `evaluacion/`. Un test de paridad compara el patrón y las constantes con `armar_muestra.py` cuando sus dependencias están instaladas, y se saltea si no.

**Verificación contra el RAR con 7-Zip (`rar7z.py`, solo listado):**
- Busca, en orden, la variable `SIETE_ZIP`, `7z`/`7zz` en `PATH` y `%ProgramFiles%\7-Zip\7z.exe`.
- Lista las entradas con `7z l -slt -ba` (`Path`, `Size`, `CRC`) y rechaza rutas absolutas o con `..`.
- **No extrae.** Para cada archivo seleccionado de `extraidos/`, compara su tamaño y su CRC32 (calculado con `zlib.crc32`) con la entrada del RAR, y además registra su SHA-256.
- Registra la versión de 7-Zip en `ejecucion`. Funciona igual en Windows y en Linux (`p7zip`/`7zz`).

**Validez de una grabación:**
- WAV completo de 16 kHz, **2 canales**, PCM16 y sin compresión, leído completo (los bytes leídos tienen que coincidir con los cuadros declarados).
- Anotaciones `.channel1.phrases` y `.channel2.phrases`, las dos presentes.
- Exceso terminal de cada anotación sobre la duración del WAV `<= 0.01 s` (`TOLERANCIA_FIN_FIGSHARE_S`).
- Anotación bien formada (criterios del Hito 2):
  - tres campos separados por tabulador y texto no vacío;
  - tiempos finitos y `0 <= start < end`;
  - `start >= fin_anterior - 1e-4`.

Lo que no cumple queda `excluida`, con un motivo legible.

**Conversión a mono:** se lee el WAV estéreo con `wave`, sin modificarlo; se hace `int32(izquierda) + int32(derecha)`, `floor_divide` por 2 e `int16`; y se escribe con `wave` (16 kHz, mono, PCM16, con los mismos cuadros). Es la misma fórmula del Hito 2, determinista, con el mismo SHA-256 en cualquier sistema. Reproduce lo que hace la aplicación, que entrega a la Etapa 2 un WAV mono de 16 kHz. No se usa FFmpeg para convertir.

**Correspondencia canal ↔ hablante:** canal izquierdo = `channel1` = `figshare_v2_S26_canal1`, y canal derecho = `channel2` = `figshare_v2_S26_canal2`. Para `s26.objects.04` se comprobó por correlación con los WAV separados. La preparación vuelve a comprobarlo en cada grabación: la correlación de cada canal con su `channelN.wav` tiene que ser mayor que con el otro, y queda registrada en el manifiesto. Los WAV separados se usan solo para esta comprobación, no como entrada del modelo.

> **Ampliación a S26 completo (08/11/2026, decisiones aprobadas).**
> - En 9 tareas (06, 07, 10, 11, 14, 15, 17, 20 y 24), los dos WAV separados tienen **1 cuadro más** que el completo. Ese cuadro sobra al final: comparando desde el inicio, la correlación es 0,9999 con su canal y menor que 0,08 con el otro; con un desfase de 1 cuadro baja a 0,89–0,95. Se admite una diferencia de 0 o 1 cuadro al final (`TOLERANCIA_CUADROS_SEPARADO = 1`): la correlación se calcula sobre los cuadros en común y el manifiesto registra `cuadros_separado` y `diferencia_cuadros`. Cualquier otra diferencia excluye la grabación. No cambia la entrada del modelo ni la referencia.
> - `politica_etiquetas.json` clasifica `-?` (tareas 09 y 18) y `?-` (tarea 12) como `habla`. Son vocalizaciones breves, de 0,03 a 0,13 s, en el canal 2.

**Indicador de cobertura de la anotación** (solo indicio, no cambia la referencia):
- **Energía por canal:** se calcula en ventanas de 30 ms (paso de 10 ms) sobre el canal correspondiente del WAV estéreo.
- **Piso de ruido:** el percentil 20 de la energía del canal dentro de sus intervalos `#`.
- **Umbral:** el piso de ruido + 12 dB.
- **Posible habla sin anotar:** ventanas sobre el umbral dentro de un `#` del canal, **fuera** de la habla anotada del otro canal, para no contar la voz del otro hablante que se filtra al micrófono. Se cuentan solo los tramos de 0,3 s o más.
- **Habla anotada con energía baja:** proporción del habla anotada del canal por debajo del umbral.
- **Registro:** los parámetros y los resultados (segundos e intervalos) van al manifiesto y al reporte de calidad, como indicio a revisar.

**Referencia (supuesto 4, resuelto):**

| Caso | Tratamiento |
|---|---|
| Texto `#` | Silencio marcado: se excluye (igual que `normalizar_muestra.py`) y se cuenta |
| Texto con al menos una letra (incluye muletillas y palabras cortadas) | Habla del participante del canal |
| Texto sin letras distinto de `#` (por ejemplo, símbolos o marcas entre corchetes) | Se busca en `politica_etiquetas.json` (`habla` o `excluir`). Si no está, la preparación **falla** y lista cada etiqueta con su cantidad. `--inventario` la lista sin preparar nada |
| Intervalos del mismo canal superpuestos o contiguos (por la tolerancia de orden de 1e-4) | Se unen en uno y se cuenta la unión |
| Intervalos de canales distintos superpuestos | Se conservan: es habla superpuesta y se puntúa |
| `end` mayor que la duración real de la mezcla por 0,01 s o menos (tolerancia del Hito 2) | Se ajusta a la duración real en la referencia de evaluación. La anotación original no cambia, y el manifiesto registra el canal, la línea, `fin_original_s` y `fin_ajustado_s` |
| `end` mayor que la duración de la mezcla por más de 0,01 s | La grabación ya quedó excluida por el criterio de validez |

- **Hablantes:** `figshare_v2_S26_canal<C>`.
- **Formato:** RTTM con tiempos a 3 decimales, ordenado por `(start, speaker)`.
- **Validación antes del DER:** segmentos con `0 <= start < end <= duración`, hablante no vacío, sin duplicados y al menos un segmento de habla. Si no se cumple, `der_estricto` y `der_tolerancia` quedan en `null` con el motivo, y no se informa ningún valor.
- **Duración real:** son los cuadros del WAV estéreo, que son los mismos del mono, divididos por 16000, sin redondear. El ajuste se hace contra ese valor, y los tiempos del RTTM se escriben a 3 decimales sin superarlo.

**Manifiesto (versionado, sin texto de las anotaciones), en dos secciones:**

```json
{
  "contenido_sha256": "<SHA-256 de la serialización canónica de 'contenido'>",
  "contenido": { ...deterministas... },
  "ejecucion": { ...variables... }
}
```

| Sección | Campos | Regla |
|---|---|---|
| `contenido` (determinista) | **Generales:** `origen: figshare:22647313:v2`, `licencia: CC BY 4.0`; originales (bytes, MD5, SHA-256 de los RAR); `politica_etiquetas_sha256`; tolerancias (`fin_s: 0.01`, `orden_s: 1e-4`); `formula_mono`; parámetros del indicador de cobertura; sesión `S26` y `seleccion`. **Por grabación:** `recording_id`, tarea, estado y motivo; archivos usados (ruta en `extraidos/`, entrada del RAR, tamaño, CRC32 y SHA-256); `cuadros` del WAV estéreo y del mono (enteros); correlación de cada canal con su `channelN.wav`; exceso terminal; conteos; `ajustes_fin` con `{canal, linea, fin_original_s, fin_ajustado_s}`; indicador de cobertura por canal; SHA-256 del WAV mono y del RTTM | Con los mismos originales, política, tolerancias y selección, tiene que ser **idéntico byte a byte** |
| `ejecucion` (variable) | fecha y hora, sistema operativo, versión de Python, versión de 7-Zip, versión del script y commit, ruta de la caché, tiempo de preparación | Se registra para trazabilidad, pero **no** forma parte de la comparación |

- **Serialización canónica de `contenido`:** UTF-8, `sort_keys=True`, `ensure_ascii=False`, `separators=(",", ":")` para el hash, listas ordenadas por `recording_id` y nombre de entrada, y fin de línea `\n`. Las duraciones se guardan como **cuadros enteros**, y los segundos (`cuadros / 16000`) son solo de lectura. Así no dependen del formato de los floats. Los tiempos de `ajustes_fin` se copian tal como están en la anotación (`fin_original_s` como texto original y como número).
- **Por qué la versión de 7-Zip, el commit y la fecha van en `ejecucion`:** no alteran los derivados. El tamaño, el CRC32 y el SHA-256 de cada archivo usado están en `contenido`. Si `extraidos/` cambiara, se notaría ahí, y la verificación contra el RAR fallaría.
- **`--verificar`** recalcula los SHA-256 de `datos/figshare_test/` y `contenido_sha256`, y los compara con el manifiesto sin tocar los originales. Ignora `ejecucion`. El nivel 3 lo ejecuta antes de evaluar.

### 12. Calidad (DER, JER) y compatibilidad CPU/GPU

> **Alcance del nivel 2 frente al nivel 3 (decisión del 08/11/2026).** Las grabaciones propias del nivel 2 tienen una secuencia de hablantes conocida, y solo validan la integración y un comportamiento básico (tarea 5.5). **La evaluación de calidad es la del nivel 3**, con la referencia anotada de Figshare. Se avanza **una tarea por vez**. El dataset ya está extraído en la caché del Hito 2 y no se descarga. Correr el modelo, la corrida diagnóstica o varias grabaciones en la máquina de desarrollo, que solo tiene CPU, requiere autorización explícita.

- **DER (B), dos métricas con nombre propio:**

  | Nombre en el reporte | Parámetros de `DiarizationErrorRate` | Tolerancia por lado | Uso |
  |---|---|---|---|
  | `der_estricto` | `collar=0.0, skip_overlap=False` | 0 s | Cada borde cuenta |
  | `der_tolerancia` | `collar=0.5, skip_overlap=False` | ±0,25 s (criterio NIST) | Misma tolerancia por lado que `md-eval -c 0.25` |

  Para cada métrica se usa una instancia distinta, acumulada por sesión (`abs(metrica)`). El reporte agrupa cada métrica en su propio bloque, por grabación y por sesión: `{"metrica", "criterio", "herramienta", "collar_pyannote_s", "tolerancia_por_lado_s", "incluye_solapamiento": true, "valor", "falsa_alarma_s", "habla_perdida_s", "confusion_s", "total_referencia_s"}`, con `herramienta` igual a `"pyannote.metrics <versión>"`. `der_estricto` lleva `criterio: "estricto"`, `collar_pyannote_s: 0.0` y `tolerancia_por_lado_s: 0.0`. `der_tolerancia` lleva `criterio: "NIST"`, `collar_pyannote_s: 0.5` y `tolerancia_por_lado_s: 0.25`. No hay ningún campo `der` suelto. No hay umbral.

  **Semántica del collar:** en `pyannote.metrics`, `collar` es el ancho **total** de la zona excluida alrededor de cada borde de la referencia, repartido mitad antes y mitad después. En `md-eval` de NIST, en cambio, `-c` es la tolerancia por lado. Por eso ±0,25 s se pide a pyannote como `collar=0.5`. Las constantes se definen una sola vez en `der.py` (`TOLERANCIA_NIST_POR_LADO_S = 0.25` y `COLLAR_NIST_PYANNOTE_S = 2 * TOLERANCIA_NIST_POR_LADO_S`), y tests de nivel 1 verifican la semántica con bordes desplazados 0,2 s y 0,4 s (tarea 7.1).

  **Alcance de la equivalencia con NIST:** `collar=0.5` reproduce la **tolerancia por lado** de `md-eval -c 0.25`, pero no garantiza los **mismos valores numéricos**. Las dos herramientas pueden diferir en:
  - cómo se combinan los collars de bordes cercanos o de hablantes superpuestos;
  - el tratamiento de la región evaluada (UEM) y del habla superpuesta;
  - la discretización y el redondeo del tiempo;
  - el criterio de desempate al asociar hablantes.

  Por eso `der_tolerancia` se informa como "DER de `pyannote.metrics` con tolerancia NIST de ±0,25 s", con la herramienta y su versión, y **no** como un resultado de `md-eval`. Este change no corre `md-eval` ni valida contra él. Comparar con DER publicados es orientativo.
- **JER:** `pyannote.metrics.diarization.JaccardErrorRate(collar=0.0, skip_overlap=False)`, por grabación y acumulado por sesión. Se registra como `jer`, con `collar_pyannote_s: 0.0`, `incluye_solapamiento: true`, la herramienta y su versión, y el error de cada hablante de la referencia. A diferencia del DER, no lo dominan los hablantes con más tiempo.
- **Componentes y dispersión:**
  - Para cada DER: `falsa_alarma_s`, `habla_perdida_s`, `confusion_s` y `total_referencia_s`, y cada componente también como proporción.
  - Por sesión y en total: el valor acumulado, ponderado por el tiempo (como acumula `pyannote.metrics`).
  - Sobre las grabaciones: la mediana, el primer y el tercer cuartil, y la peor grabación, para DER estricto, DER con tolerancia y JER.
- **Ampliación del reporte (08/11/2026):**
  - La región evaluada (UEM) es `[0, duración]` en todas las grabaciones.
  - Por grabación se registran la duración del audio, el habla de la referencia (unión y suma por hablante) y el habla superpuesta.
  - También se registra la **cobertura NIST**: el habla de referencia evaluada con `collar=0.5` frente a la evaluada sin collar, y su proporción.
  - **Error con y sin solapamiento:** los componentes del `der_estricto` se separan en la región con 2 hablantes o más en la referencia y en el resto de `[0, duración]`. Se fija el emparejamiento óptimo global de la grabación y se cuenta con `IdentificationErrorRate`, sin volver a optimizar, así que las dos regiones suman exactamente los componentes de la grabación.
  - Los estadísticos sobre grabaciones (media, mediana, cuartiles, mínimo, máximo, desviación estándar muestral, mejor y peor) son **sin ponderar**. Los acumulados están ponderados por el tiempo.
  - El JER acumulado es la media del error de todos los hablantes de referencia, como hace `abs(JaccardErrorRate)`.
  - Una corrida anterior **se reutiliza** si es compatible: par JSON/meta consistente, el mismo WAV mono por SHA-256, modelo, versiones de torch y pyannote.audio, `num_speakers` y dispositivo. `--rehacer` obliga a diarizar otra vez.
- **Cantidad de hablantes:** por grabación, `hablantes_referencia` (2), `hablantes_detectados` y `cantidad_coincide`. En total, la proporción de grabaciones en que coinciden.
- **Corrida principal y diagnóstica:**
  - La corrida **`principal`**, sin `num_speakers`, es como funciona el producto, y siempre se ejecuta.
  - La corrida **`diagnostico_num_speakers`**, con `num_speakers=2`, se ejecuta **solo si se pide** (`--diagnostico`). Separa el error de **estimar la cantidad** del de **segmentar y asignar**, y nunca se informa como resultado del producto.
  - La **primera evaluación** (`s26.objects.04`, en CPU) usa solo la principal. La diagnóstica duplica el tiempo de cómputo, por lo que se autoriza aparte.
- **Dispositivo:** la evaluación de calidad (marker `calidad`) corre en **CPU o GPU** con el mismo código, y registra `dispositivo` y `tiempo_s`. Las métricas no dependen del dispositivo, como ya probó la compatibilidad funcional. Las comprobaciones propias de CUDA (memoria y `dispositivo: cuda`) quedan en `tests/test_evaluacion_gpu.py` (marker `gpu`), pendientes para un integrante con GPU.
- **Criterios de interpretación** (sin umbral, como dice la PoC en §2.3):
  1. **La confusión con tolerancia** es lo más informativo: mide si se atribuye bien quién habla, que es lo que usan la Etapa 4 y la minuta.
  2. Si la habla perdida y la falsa alarma son mucho mayores en el DER estricto que con tolerancia, la diferencia viene de los bordes y de la granularidad de la referencia, no del modelo.
  3. Si la cantidad de hablantes no coincide, se compara con la corrida diagnóstica. Si con `num_speakers=2` el error baja mucho, el problema está en la estimación de la cantidad.
  4. Los valores son la **línea de base** de la PoC para comparar cambios futuros. La comparación con DER publicados de otros corpus es solo orientativa.
- **Limitaciones que el reporte declara** (bloque `limitaciones`):
  - la referencia anota **frases transcritas por canal**, no turnos de habla, así que puede incluir pausas internas y omitir expresiones breves no transcritas;
  - no se midió el **acuerdo entre anotadores**;
  - la **transcripción de S26 puede estar incompleta**: el README de `wavs/` dice que S26–S30 vienen de `annotations_incompleto`. El reporte incluye el resultado del indicador de cobertura;
  - hay **2 hablantes por sesión**, así que no evalúa el caso de 3 o más;
  - el **dominio es un juego**, no una reunión.
- **Decisiones aprobadas:**
  - La política de etiquetas: `#` se excluye, el texto con letras es habla y las etiquetas sin letras van a `politica_etiquetas.json`, con fallo si alguna queda sin clasificar.
  - La compatibilidad CPU/GPU sobre un subconjunto.
  - La mezcla con la fórmula del Hito 2.
  - ~~Que no se usan los WAV "sin separar canales".~~ **Reemplazada el 08/11/2026:** se usa el WAV estéreo completo de S26, convertido a mono, y los separados solo sirven para verificar la correspondencia entre canal y hablante.
  - (08/11/2026) Dataset: S26, empezando por `s26.objects.04`; fuente: `extraidos/` verificado contra el listado del RAR (sin extraer); indicador de cobertura de la anotación antes de interpretar.
  - Que se versionan solo el manifiesto y la política.
  - (08/11/2026) Agregar JER, componentes y dispersión, cantidad de hablantes y la corrida diagnóstica con `num_speakers=2`.
  - (08/11/2026) Permitir la evaluación de calidad en CPU, dejando las pruebas de CUDA para un integrante con GPU.
  - (08/11/2026) Reformular la tarea 5.5 como verificación automática básica con sus limitaciones.
- **Contrato (A):** `contrato.validar_diarizacion` sobre el 100 % de las salidas del nivel 3.
- **Compatibilidad CPU/GPU (funcional y de contrato, no de precisión):** comprueba que el mismo código corre en los dos dispositivos y que las dos salidas cumplen el contrato. **No** evalúa si la precisión es equivalente: no exige que coincidan los segmentos, la cantidad de hablantes ni el DER, y no calcula el DER de la salida en CPU.
  - Correr toda la selección también en CPU multiplicaría el tiempo, así que se ejecuta en CPU **la primera grabación válida de la selección**, por orden de tarea.
  - Las dos ejecuciones tienen que terminar con éxito y cumplir el contrato.
  - Como información, sin calificarla, se registran la cantidad de hablantes y de segmentos de cada salida y el tiempo de cada una.

## Risks / Trade-offs

- [`torchcodec` no encuentra las DLL de FFmpeg en Windows] → **Ocurrió y está resuelto.** Se usa FFmpeg 7.1.1 *shared* registrada con `os.add_dll_directory` desde un `.pth` del venv, porque `PATH` no alcanza (§8). El módulo informa el error como etapa `decodificacion` y `verificar_entorno.py` lo detecta antes de diarizar. Si reapareciera sin solución, el equipo decide sobre `soundfile`.
- [`torchcodec 0.7` solo acepta FFmpeg 4 a 7, y la de la máquina de desarrollo es la 9.0.2] → **Ocurrió y está resuelto.** La FFmpeg 7.1.1 local convive con la 9.0.2, que sigue en el `PATH` de la consola. No cambió el código.
- [Las máquinas con GPU (Linux) tienen una FFmpeg 8 o más nueva] → `verificar_entorno.py --gpu` lo detecta. Se usa una build *shared* 7.1 con `LD_LIBRARY_PATH` solo en la sesión (README). Pendiente de verificar.
- [El `.pth` falta, o no se ejecuta porque su línea no empieza con `import`, y TorchCodec no encuentra FFmpeg] → `verificar_entorno.py` falla, tanto por la importación como por la decodificación (comprobado borrando el `.pth`).
- [El entorno del paso 1 no está instalado en la máquina de desarrollo (el `.venv` de la raíz es 3.12 y no tiene `sounddevice`, `soundfile` ni PySide6)] → Tarea 5.1. El README del paso 1 usa rutas de Linux (`.venv/bin/python`); en Windows es `.venv\Scripts\python.exe`.
- [Hay etiquetas especiales desconocidas en las anotaciones (no se pudieron inspeccionar: la caché no está en la máquina de desarrollo)] → La preparación falla si encuentra una sin clasificar, y `--inventario` permite clasificarla antes. La política queda versionada.
- [La salida de `7z l -slt` cambia entre versiones o idiomas] → Se parsea solo `Path`, `Size` y `CRC`, que no se traducen. La versión de 7-Zip queda en el manifiesto y hay un test con un RAR sintético cuando 7-Zip está disponible.
- [La lógica replicada del Hito 2 se desvía de la original] → Test de paridad y tolerancia importada, no copiada.
- [Las sesiones completas tardan en la GPU] → Se registra el tiempo por grabación. La compatibilidad en CPU usa un subconjunto.
- [La CPU es lenta en el nivel 2] → Grabaciones de 30 a 60 s.
- [CPU y GPU dan segmentos distintos] → Se exige el mismo contrato, no igualdad.
- [Conflicto de PyTorch con la Etapa 3] → `torch==2.8.0` fijo y coordinación con Felipe.
- [Par inconsistente si el proceso muere entre los dos `os.replace`] → `diarization_sha256` y `validar_par`.
- [Eco del paso 1 con parlantes] → No se corrige aquí. Se registra en el nivel 2.
- [Falta de memoria en 6 GB] → Error explícito, liberación en el `finally` y `vram_pico_mib`.
- [La liberación de la GPU no se puede probar sin GPU] → Solo la cubre el nivel 3, y la tarea lo dice.

## Migration Plan

No aplica: es un módulo nuevo. Para deshacerlo, se borran `PoC/paso2_diarizacion/` y su excepción en `.gitignore`.

## Open Questions

- ¿Dónde vive el entorno compartido de las etapas 2 y 3? Solo afecta la ruta que figura en el README.
- ¿Qué compañero con GPU corre el nivel 3? No cambia lo que se construye.
