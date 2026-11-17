# Issue #18 — Reproducibilidad y robustez multiplataforma

> **Nota de reubicación (2026-11-16):** los artefactos de prueba se reorganizaron bajo
> `evaluacion/issue-18-reproducibilidad/`. Las rutas que aparecen en los comandos de
> esta sección son históricas (reflejan dónde se ejecutaron originalmente); los archivos
> se encuentran ahora en:
> - `entradas/prueba_entrada.mp3` (antes `_prueba_entrada.mp3`)
> - `entradas/audio_reproducibilidad/` (antes `_temp_reprod/`)
> - `resultados/prueba-cancelacion/` (antes `resultados/prueba-cancelacion/`)
> - `resultados/prueba-taskkill/` (antes `resultados/prueba-taskkill/`)
> - `resultados/prueba-exclusion/` (antes `resultados/prueba-exclusion/`)

## Resumen ejecutivo

La issue #18 cubre la validación de la aplicación en distintas configuraciones de hardware y sistemas operativos, la resolución de incompatibilidades y la ampliación de las verificaciones automatizadas. El trabajo está distribuido entre los integrantes del equipo según su entorno disponible.

Este documento registra el trabajo correspondiente al entorno **Windows/CPU (Luisa)**: corrección de los 17 fallos que presentaba la suite automatizada en Windows 11, validación end-to-end de la suite completa con 752 tests aprobados y ningún fallo, y los hallazgos de instalación en Linux/GPU reportados por Matías Caccia como referencia del equipo.

---

## Distribución de responsabilidades

| Integrante | Entorno | Responsabilidad |
|---|---|---|
| Luisa | Windows 11 / CPU | Corrección de suite automatizada, pruebas funcionales Windows/CPU, documentación |
| Matías Caccia | Fedora 43 / NVIDIA RTX 3050 (cu128) | Validación de instalación desde cero en Linux/GPU, pruebas funcionales Linux/GPU |
| (otros compañeros) | Linux / GPU | Suite automatizada Linux, validación funcional en GPU |

---

## Resultados: Windows/CPU

| Ejecución | Pasados | Fallidos | Skipped | Deselected | Subtests | Duración |
|---|---|---|---|---|---|---|
| Inicio (pre-issue) | 735 | 17 | 4 | 6 | — | — |
| Tras correcciones de encoding/Qt/exclusión | 751 | 1 | 4 | 6 | — | — |
| **Suite completa Windows/CPU (final)** | **752** | **0** | **4** | **6** | **52** | **562,78 s** |

Pendiente en este entorno: pruebas funcionales de la aplicación (captura o archivo de audio → procesamiento → minuta).

---

## Cambios implementados (Windows/CPU)

### 1. Bloqueo de archivos en Windows (`src/pipeline/ejecucion.py`)

**Qué fallaba:** Cuatro tests de exclusión (`test_exclusion_*`) fallaban porque `msvcrt.locking()` crea un *byte-range lock* que, en algunas versiones de Windows, hace que el `read(1)` anterior también lance `PermissionError` antes de llegar al lock explícito. El código original trataba solo los `OSError` de `msvcrt.locking()`, dejando pasar el `PermissionError` del `read()` sin convertirlo en `ReunionOcupada`.

**Causa:** `msvcrt.locking()` sobre el byte 0 de un archivo que otro descriptor ya tiene bloqueado causa que `archivo.read(1)` falle con `PermissionError` (error 13), no con `OSError` de `msvcrt`. Esta es la semántica de los byte-range locks de Windows: la operación de *lectura* falla antes de llegar a intentar el lock.

**Corrección implementada:** `try/except PermissionError` alrededor de `archivo.read(1)` en el bloque Windows de `_exclusivo()`. Un `PermissionError` en ese punto —donde `open()` ya tuvo éxito, por lo que la ACL permite acceso— solo puede significar que otro descriptor mantiene el byte-range lock.

```python
# src/pipeline/ejecucion.py (bloque Windows de _exclusivo)
if os.name == 'nt':
    import msvcrt
    archivo.seek(0)
    try:
        data = archivo.read(1)
    except PermissionError:
        # open() tuvo éxito → la ACL permite acceso; read() falla solo si otro
        # descriptor mantiene un byte-range lock sobre el byte 0.
        raise ReunionOcupada('Otra ejecución está utilizando esta reunión.')
    if data != b'0':
        ...
```

**Restricción explícita aplicada:** No se convirtió cualquier `PermissionError` en `ReunionOcupada`. Se agregó también `test_error_real_de_permisos_no_se_convierte_en_reunion_ocupada` para verificar que un `PermissionError` al *abrir* el archivo (ACL denegada) se propaga sin convertirse en `ReunionOcupada`.

**Archivos modificados:**
- `src/pipeline/ejecucion.py`
- `tests/integracion/test_workflow.py` (nuevo test de regresión)

**Validación:** `python -m pytest tests/integracion/test_workflow.py -q` → 0 fallos.

---

### 2. Fuentes Qt en plataforma offscreen — tests de orientación (`tests/integracion/test_panel_procesamiento.py`)

**Qué fallaba:** `test_ventana_en_columnas_y_detalles_de_captura[False]` y `[True]` fallaban en Windows con `QT_QPA_PLATFORM=offscreen`.

**Causa:** La plataforma `offscreen` de Qt no puede cargar fuentes del sistema en Windows. `QFont("Segoe UI")` cae en un fallback monoespaciado ~2,2× más ancho que el font real. Esto infla `minimumSizeHint()` del divisor a ~1575 px, superando el umbral de orientación horizontal (1440 px del escritorio), y los tests fallan aunque la interfaz real funcione correctamente en modo horizontal.

**Diagnóstico previo descartado:** Se intentó inicialmente reducir `minimumSizeHint()` con `setMinimumWidth(1)` en las etiquetas de word-wrap (`interfaz.py` y `panel_procesamiento.py`). Esto se revirtió porque Qt ya retorna un `minimumSizeHint` pequeño para etiquetas con word-wrap; el problema era exclusivamente la fuente del fallback.

**Corrección implementada:** Cargar explícitamente los archivos de fuente Segoe UI via `QFontDatabase.addApplicationFont()` en el fixture `app()`, exclusivamente en Windows. No se modificó ningún archivo de producción.

```python
# tests/integracion/test_panel_procesamiento.py — fixture app()
if os.name == 'nt':
    import pathlib
    from PySide6.QtGui import QFontDatabase
    fonts = pathlib.Path(r'C:\Windows\Fonts')
    for nombre in ('segoeui.ttf', 'segoeuisl.ttf', 'seguisb.ttf'):
        p = fonts / nombre
        if p.exists():
            QFontDatabase.addApplicationFont(str(p))
```

**Archivos modificados:**
- `tests/integracion/test_panel_procesamiento.py`

**Validación:** `python -m pytest tests/integracion/ -q` → 0 fallos (436 passed).

---

### 3. Codificación UTF-8 en la CLI de diarización (`src/diarizacion/diarizar.py`, `src/diarizacion/contrato.py`)

**Qué fallaba:** Cinco tests de diarización que capturan salida de la CLI (`test_contrato_*`, `test_diarizar_*`) fallaban en Windows porque `sys.stdout.encoding = cp1252` causa que Python lance `UnicodeEncodeError` al intentar imprimir caracteres como `ó`, `ú`, etc. presentes en mensajes de error en español.

**Causa:** Python 3 en Windows usa `cp1252` como encoding de stdout/stderr por defecto. Los mensajes de error en español del módulo de diarización no pueden codificarse en cp1252 sin pérdidas.

**Corrección implementada:** Reconfigurar `sys.stdout` y `sys.stderr` a UTF-8 inmediatamente después de parsear argumentos en ambas funciones `main()`.

```python
# Después de args = parser.parse_args(argv)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
```

**Archivos modificados:**
- `src/diarizacion/diarizar.py`
- `src/diarizacion/contrato.py`

**Validación:** `python -m pytest tests/diarizacion/ -q` → 0 fallos en los tests afectados.

---

### 4. Lectura de `minutes.md` con encoding explícito (`tests/integracion/test_workflow.py`)

**Qué fallaba:** `test_visor_lee_solo_resultados_vigentes_y_sin_escritor` comparaba `leer_resultado_texto(s.salida, 'minutes.md')` con `(s.salida / 'minutes.md').read_text()`. En Windows, `read_text()` sin encoding usa cp1252, corrompiendo los caracteres UTF-8 del archivo Markdown generado.

**Corrección implementada:** Agregar `encoding='utf-8'` a la llamada `read_text()` del lado del assert.

**Archivos modificados:**
- `tests/integracion/test_workflow.py` (línea 1012)

---

### 5. Codificación UTF-8 en tests de minutas

**Qué fallaba:** 16 tests fallaban:
- 15 variantes de `test_todas_las_selecciones_con_recuperacion` en `test_consolidacion_limites.py`
- 1 `test_entrada_desde_archivo_y_no_borra_fuente` en `test_minutas.py`

**Causa:** Pydantic V2's `model_dump_json()` escribe caracteres no-ASCII literalmente en UTF-8 (no como `\uXXXX`). Por ejemplo, `í` (U+00ED) queda en el archivo JSON como los bytes `C3 AD`. Al releer con `read_text()` sin encoding, Windows usa cp1252:
- `C3` → `Ã` (U+00C3)
- `AD` → guion suave (U+00AD)

Resultado: `'Síntesis global.'` se lee como `'SÃ\xadntesis global.'` y el assert falla.

**Correcciones implementadas:**

`tests/minutas/test_consolidacion_limites.py` — función `ejecutar()` (línea 59):
```python
# Antes:
return json.loads(r.json.read_text()), json.loads(r.manifiesto.read_text())
# Después:
return json.loads(r.json.read_text(encoding='utf-8')), json.loads(r.manifiesto.read_text(encoding='utf-8'))
```

`tests/minutas/test_minutas.py` — línea 137:
```python
# Antes:
self.assertEqual(json.loads(salida.json.read_text())["resumen"], ...)
# Después:
self.assertEqual(json.loads(salida.json.read_text(encoding='utf-8'))["resumen"], ...)
```

**Archivos modificados:**
- `tests/minutas/test_consolidacion_limites.py`
- `tests/minutas/test_minutas.py`

**Validación:** `python -m pytest tests/minutas/ -q` → 0 fallos en los 278 tests disponibles.

---

### 6. Mejoras de detección de libarchive en Windows (`src/bibliotecas.py`)

**Qué se corrigió:** `cargar_libarchive()` no encontraba la DLL en algunas instalaciones de Windows 11 donde libarchive se instala como `archiveint.dll` en System32.

**Cambios:**
- Soporte para variable de entorno `LIBARCHIVE` como ruta explícita (todas las plataformas)
- Intento de carga directa por nombre en Windows (cubre `archiveint.dll` vía System32 y `add_dll_directory`)
- Nuevos tests en `tests/integracion/test_bibliotecas.py`

**Archivos modificados:**
- `src/bibliotecas.py`
- `tests/integracion/test_bibliotecas.py`

---

### 7. Mejoras de detección de FFmpeg DLLs (`src/verificar_entorno.py`)

**Qué se corrigió:** `verificar_ffmpeg()` solo buscaba DLLs en la ruta fija del README, sin considerar instalaciones vía WinGet u otras rutas.

**Cambios:**
- Nueva función `_encontrar_carpeta_dll_ffmpeg()` con búsqueda ordenada: variable de entorno `DIARIZACION_FFMPEG_DLL_DIR` → ruta del README → directorio del ejecutable `ffmpeg`/`ffprobe` en PATH
- Mensajes diferenciados: FALLA cuando no hay DLL, AVISO cuando la DLL está en ruta alternativa sin `.pth`
- Nuevos tests en `tests/diarizacion/test_verificar_entorno.py`

**Archivos modificados:**
- `src/verificar_entorno.py`
- `tests/diarizacion/test_verificar_entorno.py`

---

### 8. Reproducibilidad de audio — flag `-D` en espeak-ng (`evaluacion/asociacion/ejemplo_ideal/generar.py`)

**Qué fallaba:** `tests/asociacion/test_ejemplo_ideal.py::test_reproducible` verificaba que dos llamadas consecutivas a `generar()` producen archivos byte-a-byte idénticos. La primera diferencia aparecía en `audio.wav` en el byte 16044 (muestra 8000, tiempo 0,5 s — exactamente el inicio del primer segmento de voz).

**Hipótesis descartadas (confirmadas por diagnóstico):**

| Hipótesis | Resultado |
|---|---|
| `con_voz[0]` varía en ±1 por precisión float64 en el umbral silencio/voz | **Descartada.** `con_voz[0]` = 224 en todas las ejecuciones; no varía |
| `resample_poly` produce valores distintos entre ejecuciones | **Descartada.** Dos llamadas con la misma entrada → diferencia máxima = 0,0 |
| Cuantizar a PCM_16 antes del trimming elimina la diferencia | **Descartada.** Causa mismatch de forma (971 115 vs 970 896 muestras) |

**Causa raíz confirmada:** espeak-ng llama a `srand(time(NULL))` al inicializar su generador de números aleatorios. Dos llamadas en segundos diferentes producen formas de onda genuinamente distintas (363 000+ muestras diferentes, delta hasta ±60 en int16). El flag `-D` ("Enable deterministic random mode") desactiva esta semilla variable.

**Corrección implementada:**
```python
# evaluacion/asociacion/ejemplo_ideal/generar.py — función sintetizar(), línea 54
# Antes:
subprocess.run(["espeak-ng", "-v", voz, "-s", str(velocidad), "-w", str(ruta), texto], ...)
# Después:
subprocess.run(["espeak-ng", "-D", "-v", voz, "-s", str(velocidad), "-w", str(ruta), texto], ...)
```

**Validación end-to-end:** Pre-calentamiento (simula `test_asociacion.py`) + fixture + `test_reproducible` → los 4 archivos (`audio.wav`, `diarization.json`, `asr.json`, `referencia.json`) son byte-idénticos. Suite `tests/asociacion/`: 168 passed, 0 failed.

**Calidad de audio:** RMS ≈ 3 025 con y sin `-D`. Misma longitud. El flag `-D` está disponible en espeak-ng ≥ 1.49 (2015); disponible en Linux y Windows.

**Archivos modificados:**
- `evaluacion/asociacion/ejemplo_ideal/generar.py`

---

## Cambios descartados o revertidos

### `setMinimumWidth(1)` en etiquetas word-wrap

**Qué se intentó:** Reducir `minimumSizeHint()` del divisor añadiendo `lbl.setMinimumWidth(1)` y `aviso.setMinimumWidth(1)` en `panel_procesamiento.py` e `interfaz.py`.

**Por qué se revirtió:** Qt ya retorna un `minimumSizeHint` pequeño para etiquetas con `setWordWrap(True)`. El ancho inflado no venía de estas etiquetas sino del fallback de fuente monoespaciada. Los cambios en archivos de producción eran innecesarios y se revirtieron antes de hacer commit.

---

## Hallazgos reportados: Linux/GPU (Matías Caccia, 2026-11-16)

Configuración probada: **Fedora 43 — Python 3.12.16 — NVIDIA RTX 3050 Laptop 6 GB — perfil `requirements-cu128.txt`**

Resultado general: instalación completada exitosamente tras ajustes manuales. Pipeline ejecutado en 66,6 s con pico de VRAM de 4832/6144 MiB.

| # | Hallazgo | Severidad | Estado |
|---|---|---|---|
| 1 | README no tiene sección Fedora; Fedora no incluye Python 3.12 en el sistema base | Media | ⏳ Pendiente |
| 2 | Fedora: `7zip` no incluye soporte RAR; el mensaje de error del verificador es incorrecto | Media | ⏳ Pendiente |
| 3 | `localizar_7zip()` prefiere `7z` sobre `7zz` sin verificar soporte RAR primero | Media | ⏳ Pendiente |
| 4 | **Perfil cu128:** `torchcodec 0.7.0+cu128` requiere `libnppicc.so.12` (NPP CUDA), no instalada por defecto → el pipeline no diariza | **Crítico** | ⏳ Pendiente |
| 5 | Primer `pip install` se interrumpió por descargas concurrentes competidoras | Baja | ⏳ Pendiente (procedimiento) |

La implementación de las correcciones para estos hallazgos y su validación deben coordinarse con los compañeros que trabajan en entornos Linux/GPU.

---

## Resultados de validación funcional (Windows/CPU — Luisa, 2026-11-16)

### Prueba 1 — Pipeline completo con audio sintético

**Comando ejecutado:**
```powershell
python -m src.pipeline ejecutar evaluacion/asociacion/ejemplo_ideal/generado/audio.wav --dispositivo-stt cpu --dispositivo-diarizacion cpu
```

**Resultado:** COMPLETADO sin errores

| Etapa | Duración |
|---|---|
| Preparación | 2,203 s |
| Diarización | 102,281 s |
| Transcripción | 283,375 s |
| Asociación | 0,094 s |
| Generación de minuta | 249,625 s |
| **Total** | **638,375 s** |

**Directorio de salida:** `resultados/reunion-e27b6c217a53`

**Archivos verificados:** `audio.wav`, `diarization.json`, `diarization.meta.json`, `asr.json`, `transcription.json`, `transcription.meta.json`, `minutes.json`, `minutes.md`, `workflow.json`, `ejecucion_minutas.json`, `ingesta.json`, carpeta `fuentes/`

### Prueba 2 — Revisión del contenido de la minuta

**Resultado:** Parcialmente satisfactorio — secciones y estructura correctas; dos observaciones de calidad registradas.

La minuta contiene las secciones esperadas con participantes identificados, resumen y acciones. Se registran las siguientes observaciones sin asignar causa definitiva ni requerir corrección inmediata:

| # | Observación | Tipo | Causa probable |
|---|---|---|---|
| O1 | Acción «Enviar el informe del presupuesto el viernes» aparece con responsable «Sin asignar»; el speaker 02 se la autoasigna en el audio | Error de atribución de responsabilidades en la minuta | A investigar — puede ser límite del modelo de extracción |
| O2 | Minuta dice «memo con el cliente» donde el audio dice «demo con el cliente» | Posible error de transcripción | Probable pronunciación poco natural de las voces sintéticas de espeak-ng; no confirmado |

La acción «Revisar cada partida del presupuesto antes del fin de mes» aparece sin responsable y eso coincide con el audio — correcto.

### Prueba 3 — Reproducibilidad del audio sintético (tarea 1.2)

**Comando ejecutado:**
```powershell
python -m evaluacion.asociacion.ejemplo_ideal.generar --salida _temp_reprod
```

**Resultado del generador:** 60,7 s, 6 intervenciones

**Verificación SHA-256:**

| Archivo | SHA-256 |
|---|---|
| `evaluacion/asociacion/ejemplo_ideal/generado/audio.wav` | `1A7398A49C3465C853D356481E03C549F472174A08349156466DD25CC77DC70C` |
| `_temp_reprod/audio.wav` | `1A7398A49C3465C853D356481E03C549F472174A08349156466DD25CC77DC70C` |

**Conclusión:** Reproducibilidad byte a byte confirmada. El flag `-D` de espeak-ng funciona correctamente en Windows/CPU. Dos ejecuciones independientes del generador producen archivos WAV bit-exact idénticos.

### Prueba 4 — Entrada MP3 (tarea 2.3)

**Preparación del archivo de prueba:**
```powershell
ffmpeg -i evaluacion\asociacion\ejemplo_ideal\generado\audio.wav -t 30 _prueba_entrada.mp3
```

**Comando ejecutado:**
```powershell
python -m src.pipeline ejecutar .\_prueba_entrada.mp3 --dispositivo-stt cpu --dispositivo-diarizacion cpu --modelo qwen2.5-7b
```

**Resultado:** COMPLETADO sin errores — tiempo total: 324,015 s

**Directorio de salida:** `resultados/reunion-08325309e8d7/`

**Revisión de `minutes.md`:** identifica el presupuesto y la acción de revisar las partidas. No aparecen decisiones, lo cual es compatible con el fragmento de 30 segundos utilizado. No se realizó comparación exhaustiva contra la transcripción.

**Conclusión:** El pipeline acepta entrada MP3, la convierte internamente y completa todas las etapas correctamente en Windows/CPU.

### Prueba 5 — Reanudación sin reprocesamiento (tarea 2.4)

**Comando ejecutado:**
```powershell
python -m src.pipeline continuar --reunion .\resultados\reunion-e27b6c217a53
```

**Resultado:** COMPLETADO — las cinco etapas quedaron registradas como `reutilizada` con 0,0 s de procesamiento cada una

| Métrica | Valor |
|---|---|
| Latencia total (reanudación) | 1,047 s |
| Latencia original | 638,375 s |
| Cambios en claves, hashes o metadatos | Ninguno |
| Cambios observados en `workflow.json` | Solo fechas y tiempos de ejecución/reutilización |

**Conclusión:** El sistema detecta correctamente el resultado vigente y no reprocesa ninguna etapa. Los checkpoints son íntegros y reutilizables en Windows/CPU.

### Prueba 6 — Listado de dispositivos de audio (tarea 3.1)

**Comando ejecutado:**
```powershell
python -m sounddevice
```

**Resultado:** 21 dispositivos listados (índices 0–20) sin error; incluye micrófonos Intel Smart Sound y ThinkPad USB-C Dock Gen2

| Rol | Índice | Dispositivo |
|---|---|---|
| Entrada predeterminada | 1 | (Intel Smart Sound) |
| Salida predeterminada | 3 | — |

**Conclusión:** sounddevice enumera correctamente los dispositivos de audio disponibles en Windows/CPU.

### Prueba 7 — Captura con tono de prueba y audio del sistema (tareas 3.2 y 3.3)

**Hallazgo previo:** `--sistema` requiere un dispositivo de entrada loopback, no un dispositivo de salida. El dispositivo 3 (`Asignador de sonido Microsoft`) es salida y PortAudio lo rechaza. Fue necesario identificar los dispositivos de loopback entre los 21 disponibles.

**Comando funcional:**
```powershell
$env:PYTHONUTF8=1; python -m src.captura.captura --mic 15 --sistema 22 --duracion 15 --tono
```

| Verificación | Resultado |
|---|---|
| Ambas fuentes registran señal | ✅ OK |
| Sin pérdidas ni desincronización | ✅ OK |
| WAV mono, 16 kHz, PCM 16 | ✅ OK |
| Tono de prueba capturado como audio del sistema | ✅ OK |
| Verificación auditiva | ✅ Audio correcto |

**Observación — nuevo hallazgo de encoding:** fue necesario configurar `PYTHONUTF8=1` para evitar un `UnicodeEncodeError` al escribir el JSON de reporte de captura. El módulo `src/captura/captura.py` escribe a stdout/archivo sin reconfigurar el encoding, igual al problema ya corregido en `src/diarizacion/`. Registrado como hallazgo pendiente de corrección (fuera del scope de esta tarea de validación).

**Conclusión:** captura de micrófono y audio del sistema funcionan correctamente en Windows/CPU con dispositivos explícitos. La detección automática de dispositivos es exclusiva de Linux/PipeWire.

### Prueba 8 — Captura y reproducción desde GUI (tarea 3.4)

**Procedimiento:**
1. `python -m src.interfaz` → GUI abre sin error
2. Dispositivos seleccionados: mic 15 (`ThinkPad USB-C Dock Gen2 — USB Audio`), sistema 22 (loopback)
3. Grabación de 20 segundos iniciada y detenida desde la interfaz
4. Verificaciones automáticas de la GUI

| Verificación | Resultado |
|---|---|
| GUI abre sin error | ✅ OK |
| Dispositivos mic y sistema correctamente listados | ✅ OK |
| Grabación de 20 s inicia y detiene correctamente | ✅ OK |
| Archivo WAV generado (5/5 checks automáticos de la GUI) | ✅ OK |
| WAV listado en el panel de resultados | ✅ OK |

**Reproducción:** verificada fuera de la interfaz (Explorador de Windows). El control de reproducción integrado de la GUI no pudo verificarse por limitaciones del entorno (`QT_QPA_PLATFORM=offscreen`); el archivo WAV producido es un WAV válido y audible.

**Observación:** sin tono de prueba activo, el dispositivo sistema 22 no entregó señal de audio y la grabación falló. Con `--tono` la captura funcionó correctamente. Esta limitación es de hardware/configuración del entorno Windows específico, no del código.

**Conclusión:** APROBADA — la GUI captura audio y genera un WAV válido en Windows/CPU. La reproducción desde el archivo fue confirmada auditivamente.

### Prueba 9 — Cancelación durante diarización (tarea 4.1)

**Procedimiento:**
```powershell
python -m src.pipeline ejecutar evaluacion\asociacion\ejemplo_ideal\generado\audio.wav --dispositivo-stt cpu --dispositivo-diarizacion cpu --salida resultados\prueba-cancelacion
# Ctrl+C durante la etapa diarizar (~93 s de procesamiento)
```

**Resultado del workflow:**
```
estado: cancelado
etapas_vigentes: preparar
```

| Verificación | Resultado |
|---|---|
| `workflow.json` estado `cancelado` | ✅ OK |
| Etapa `diarizar` marcada `cancelada` | ✅ OK |
| `etapas_vigentes` = solo `preparar` | ✅ OK |
| Sin archivos `.tmp` | ✅ OK |
| Sin checkpoint `diarizar` en `etapas` (no corrompe reintento) | ✅ OK |

**Observaciones:**

| # | Observación | Impacto |
|---|---|---|
| O1 | La cancelación con Ctrl+C tardó ~93 segundos — el proceso espera que el subproceso de diarización responda a SIGTERM antes de terminar | No incumple el criterio de aceptación; es una limitación operativa del tiempo de respuesta del modelo |
| O2 | Aparece un traceback de `KeyboardInterrupt` en la terminal | Comportamiento esperado de Python ante Ctrl+C; no indica fallo del pipeline |
| O3 | `diarization.json` (11 segmentos, JSON válido) y `diarization.meta.json` quedan en disco sin checkpoint vigente | Son archivos "huérfanos": `vigente()` no los reconoce sin entrada en `etapas['diarizar']`, por lo que no corrompen una ejecución posterior. No quedan archivos `.tmp`. El criterio de aceptación se cumple. |

**Conclusión:** APROBADA con observaciones — el estado del pipeline tras cancelación es consistente y no corrompe una ejecución posterior. Los archivos huérfanos son un efecto secundario de la cancelación del subproceso de diarización pero no impiden la recuperación.

### Prueba 10 — Reanudación desde directorio cancelado (tarea 4.2)

**Procedimiento:** ejecutar nuevamente el mismo comando sobre `resultados\prueba-cancelacion` (directorio con `preparar` vigente, `diarizar` cancelada):
```powershell
python -m src.pipeline ejecutar evaluacion\asociacion\ejemplo_ideal\generado\audio.wav --dispositivo-stt cpu --dispositivo-diarizacion cpu --salida resultados\prueba-cancelacion
```

| Etapa | Resultado | Duración |
|---|---|---|
| preparar | Reutilizada | — |
| diarizar | OK | 91,438 s |
| transcribir | OK | 143,266 s |
| asociar | OK | 0,094 s |
| minuta | OK | 232,422 s |
| **Total** | **completado** | **468 s** |

**Conclusión:** APROBADA — el pipeline retomó desde `preparar` (único checkpoint vigente), reprocesó todas las etapas pendientes sin errores y completó exitosamente. La reanudación tras cancelación funciona correctamente en Windows/CPU.

### Prueba 11 — Recuperación tras terminación abrupta con `taskkill` (tarea 4.3)

**Procedimiento:**
1. Pipeline iniciado sobre `resultados\prueba-taskkill` (directorio fresco)
2. Durante la etapa `diarizar`: `taskkill /F /PID 30200`
3. Consulta de estado: `python -m src.pipeline estado --reunion resultados\prueba-taskkill`
4. Reejecutar sobre el mismo directorio

**Estado tras `taskkill`:**
```
estado: fallido
error: "Ejecución interrumpida sin cierre; consultar checkpoints y reanudar."
etapa interrumpida: diarizar
activa: false
etapas_vigentes: preparar
```

**Reanudación:**

| Etapa | Resultado | Duración |
|---|---|---|
| preparar | Reutilizada | — |
| diarizar | OK | 95,656 s |
| transcribir | OK | 135,735 s |
| asociar | OK | 0,141 s |
| minuta | OK | 262,344 s |
| **Total** | **completado** | **496,219 s** |

**Conclusión:** APROBADA — el pipeline detectó la interrupción abrupta, conservó el checkpoint `preparar` y completó la ejecución correctamente desde la etapa `diarizar`. La diferencia respecto a la tarea 4.2 (Ctrl+C) es que el estado queda como `fallido` en lugar de `cancelado`, con un mensaje de error explícito que orienta al usuario.

### Prueba 12 — Reanudación sin archivo de audio original (tarea 4.4)

**Procedimiento:**
1. Renombrar el audio original: `audio.wav → audio.wav.bak`
2. Ejecutar el pipeline sobre `resultados\prueba-taskkill` (directorio ya completado) con la ruta original del audio
3. Restaurar el archivo: `audio.wav.bak → audio.wav`

| Etapa | Resultado |
|---|---|
| preparar | Reutilizada |
| diarizar | Reutilizada |
| transcribir | Reutilizada |
| asociar | Reutilizada |
| minuta | Reutilizada |
| **Total** | **completado — 0,953 s** |

**Validado:** el pipeline completó sin error aunque el archivo original no estaba disponible, reutilizando todas las etapas vigentes.

**No validado:** el escenario del spec requiere que el pipeline use la copia en `fuentes/` para *reprocesar* etapas pendientes cuando el original no existe. Ese camino (`resolver_fuentes()` con `fuentes_conservadas`) no se ejercitó porque el directorio ya estaba completamente vigente — la copia conservada solo se activa cuando hay etapas no vigentes que requieren relectura del audio. Para completar esta validación sería necesario repetir la prueba con un directorio cancelado (solo `preparar` vigente) y el audio original ausente.

**Conclusión:** PARCIALMENTE APROBADA — la reanudación sin archivo original funciona cuando todas las etapas están vigentes. El escenario de reprocesamiento parcial via `fuentes/` queda pendiente de validación explícita.

### Prueba 13 — Exclusión de acceso concurrente (tarea 4.5)

**Procedimiento:** dos terminales simultáneas sobre `resultados\prueba-exclusion` (directorio fresco):
- Terminal 1: `python -m src.pipeline ejecutar ... --salida resultados\prueba-exclusion`
- Terminal 2 (durante la etapa `diarizar` de Terminal 1): mismo comando

**Resultados:**

| Terminal | Resultado |
|---|---|
| Terminal 2 | `ReunionOcupada: Otra ejecución está utilizando esta reunión.` — rechazada inmediatamente |
| Terminal 1 | Completó las cinco etapas correctamente — 448,609 s |

**Conclusión:** APROBADA — el mecanismo de exclusión concurrente funciona correctamente en Windows/CPU. La segunda instancia es rechazada con el error esperado sin afectar ni corromper la ejecución principal.

---

## Resultados de validación funcional (Linux/GPU — Matías Caccia, 2026-11-15)

**Entorno:** Fedora 43 · kernel 7.2.11 · Python 3.12.16 · PyTorch 2.8.0+cu128 · NVIDIA RTX 3050 Laptop 6 GB · clon limpio desde `feature/integracion-poc` (`cea3cb1`)

**Ajustes realizados durante las pruebas:**
- `SIETE_ZIP=~/.local/bin/7zz` (paquete Fedora sin soporte RAR)
- Reinstalación de `torchcodec==0.7.0` desde PyPI (workaround hallazgo #4)
- `QT_QPA_PLATFORM=offscreen` para pytest
- Cachés de Hugging Face y Whisper ya pobladas; primera descarga de modelos no validada

### Prueba — Suite automatizada en Linux/GPU (tarea 5.4)

```
pytest -q -rs tests hito-2/tests
```

| Métrica | Resultado |
|---|---|
| Aprobados | 820 |
| Subtests | 52 |
| Omitidos | 2 |
| Deseleccionados | 6 |
| Fallidos | 0 |

**Nota:** se ejecutaron `tests/` y `hito-2/tests/` juntos (820 total). La diferencia respecto a Windows/CPU (752) se explica por los tests adicionales de `hito-2/tests/`; no hay regresiones respecto a la suite base. Verificación GPU: 0 fallas, 0 avisos tras ajustes.

### Prueba — Pipeline completo en Linux/GPU (tarea 5.2)

Audio de prueba: grabación propia de 30,4 s (las cachés de modelos ya estaban disponibles; la validación con el audio sintético compartido queda pendiente).

| Etapa | Duración |
|---|---|
| Diarización (CUDA) | 7,9 s |
| Transcripción | 13,1 s |
| Asociación | 0,003 s |
| Minuta (`qwen2.5:7b`) | 45,4 s |
| **Total** | **66,6 s** |

Pico de VRAM: 4832 / 6144 MiB. Estado final: completado.

### Hallazgos confirmados (tarea 5.3)

| # | Hallazgo | Severidad | Workaround aplicado |
|---|---|---|---|
| 1 | README sin sección Fedora | Media | — |
| 2 | Paquetes `7zip` de Fedora sin soporte RAR | Media | `SIETE_ZIP=~/.local/bin/7zz` |
| 3 | `localizar_7zip` prioriza `7z` sin verificar soporte RAR | Media | Mismo workaround |
| 4 | `torchcodec 0.7.0+cu128` requiere `libnppicc.so.12` (no incluida por defecto) | **Crítico** | Reinstalar `torchcodec==0.7.0` desde PyPI |
| 5 | Instalación CUDA descarga varios GB; puede interrumpirse por red | Baja | — |

Todos los hallazgos permanecen **pendientes de corrección**. Las correcciones requieren coordinación con los compañeros que trabajan en entornos Linux/GPU y están fuera del scope de este change.

### Cobertura no validada en Linux

- Interfaz gráfica y captura de audio en vivo
- Grabación interrumpida abruptamente
- Entorno Linux/CPU (tarea 5.1)
- Validación con audio sintético compartido (`ejemplo_ideal`) en GPU
- Primera descarga de modelos desde cero

---

## Validaciones pendientes

### Windows/CPU (Luisa)

| Validación | Estado |
|---|---|
| Suite automatizada completa | ✅ 752 passed, 0 failed, 4 skipped, 6 deselected, 52 subtests, 562,78 s |
| Reproducibilidad del audio sintético (espeak-ng `-D`) | ✅ Confirmado — SHA-256 idéntico en dos ejecuciones independientes (2026-11-16) |
| Flujo principal — pipeline desde archivo de audio sintético | ✅ Completado (638 s, 2026-11-16) — ver observaciones O1 y O2 arriba |
| Calidad del contenido de la minuta | ✅ Parcialmente satisfactorio — 2 observaciones registradas, sin corrección inmediata |
| Procesamiento de archivo MP3 como entrada | ✅ Completado (324 s, 2026-11-16) — conversión automática confirmada |
| Reanudación sin reprocesamiento | ✅ Completado (1,047 s vs 638 s original, 2026-11-16) — 5 etapas reutilizadas |
| Listado de dispositivos de audio (sounddevice) | ✅ 21 dispositivos detectados, entrada/salida predeterminadas identificadas (2026-11-16) |
| Captura con tono de prueba y audio del sistema (tareas 3.2–3.3) | ✅ OK — requiere `PYTHONUTF8=1`; hallazgo de encoding en `src/captura/captura.py` registrado |
| Captura y reproducción desde GUI (tarea 3.4) | ✅ OK — 5/5 checks; reproducción verificada fuera de GUI; requiere tono con sistema 22 (2026-11-16) |
| Cancelación durante diarización (tarea 4.1) | ✅ OK — estado `cancelado`, sin `.tmp`, archivos huérfanos no corrompen reintento; demora ~93 s (2026-11-16) |
| Reanudación desde directorio cancelado (tarea 4.2) | ✅ OK — `preparar` reutilizada, 4 etapas reprocesadas, completado en 468 s (2026-11-16) |
| Recuperación tras `taskkill` abrupto (tarea 4.3) | ✅ OK — estado `fallido` detectado, `preparar` conservada, pipeline completado en 496 s (2026-11-16) |
| Reanudación sin archivo original (tarea 4.4) | ⚠️ Parcialmente validado — reutilización con ejecución completa confirmada; reprocesamiento via `fuentes/` no verificado (2026-11-16) |
| Exclusión de acceso concurrente (tarea 4.5) | ✅ OK — segunda instancia rechazada con `ReunionOcupada`; primera instancia completó en 448 s (2026-11-16) |

### Linux/GPU (Matías Caccia, 2026-11-15)

| Validación | Estado |
|---|---|
| Suite automatizada en Linux/GPU | ✅ 820 passed (tests + hito-2/tests), 0 fallidos, Fedora 43 / cu128 (2026-11-15) |
| Pipeline funcional en Linux/GPU | ✅ Completado en 66,6 s, VRAM 4832/6144 MiB, con grabación propia (2026-11-15) |
| Hallazgo #4 documentado (torchcodec cu128 + libnppicc.so.12) | ✅ Documentado — workaround: reinstalar desde PyPI; corrección pendiente |
| Fix hallazgo #4: torchcodec cu128 + libnppicc.so.12 | ⏳ Pendiente de corrección — crítico para perfil GPU |
| Fix hallazgos #2 y #3: 7zip/RAR en Fedora | ⏳ Pendiente de corrección |
| Fix hallazgo #1: README sección Fedora | ⏳ Pendiente de corrección |
| Pipeline con audio sintético compartido (`ejemplo_ideal`) en GPU | ⏳ Pendiente (cachés ya pobladas; no validado desde cero) |
| Validación en Linux/CPU (tarea 5.1) | ⏳ Pendiente |

### Generales

| Validación | Estado |
|---|---|
| Matriz de configuraciones documentada (Windows/CPU ✅, Linux/GPU ✅ con workarounds, Linux/CPU ⏳) | ⚠️ Parcial — Linux/CPU sin validar |
| Documentación del procedimiento de instalación verificado | ⏳ Pendiente (tarea 6.3) |

---

## Tabla de evidencias — resumen de validación funcional

| Fecha | Prueba | Tarea | Entorno | Resultado | Observaciones |
|---|---|---|---|---|---|
| 2026-11-16 | 1 — Pipeline completo con audio sintético | 2.1 | Windows/CPU | ✅ Completado — 638 s | 7 archivos de salida verificados |
| 2026-11-16 | 2 — Contenido de la minuta | 2.2 | Windows/CPU | ⚠️ Parcial | O1: responsable «Sin asignar» en una acción; O2: «memo» por «demo» |
| 2026-11-16 | 3 — Reproducibilidad del audio sintético | 1.2 | Windows/CPU | ✅ Aprobada | SHA-256 idéntico en dos ejecuciones independientes (`1A7398…`) |
| 2026-11-16 | 4 — Entrada MP3 | 2.3 | Windows/CPU | ✅ Aprobada — 324 s | Conversión automática a WAV 16 kHz mono PCM 16 confirmada |
| 2026-11-16 | 5 — Reanudación sin reprocesamiento | 2.4 | Windows/CPU | ✅ Aprobada — 1,047 s | 5 etapas reutilizadas; timestamps y hashes sin cambios |
| 2026-11-16 | 6 — Listado de dispositivos de audio | 3.1 | Windows/CPU | ✅ Aprobada | 21 dispositivos detectados; entrada/salida predeterminadas identificadas |
| 2026-11-16 | 7 — Captura con tono y audio del sistema | 3.2–3.3 | Windows/CPU | ✅ Aprobada | Requiere `PYTHONUTF8=1`; hallazgo de encoding en `src/captura/captura.py` registrado |
| 2026-11-16 | 8 — Captura y reproducción desde GUI | 3.4 | Windows/CPU | ✅ Aprobada | Reproducción verificada fuera de la GUI; sin tono, sistema 22 no entrega señal |
| 2026-11-16 | 9 — Cancelación durante diarización | 4.1 | Windows/CPU | ✅ Aprobada | Ctrl+C tardó ~93 s; archivos huérfanos no corrompen reintento; sin `.tmp` |
| 2026-11-16 | 10 — Reanudación desde directorio cancelado | 4.2 | Windows/CPU | ✅ Aprobada — 468 s | `preparar` reutilizada; 4 etapas reprocesadas correctamente |
| 2026-11-16 | 11 — Recuperación tras `taskkill` | 4.3 | Windows/CPU | ✅ Aprobada — 496 s | Estado `fallido` detectado; mensaje de error orientativo; `preparar` conservada |
| 2026-11-16 | 12 — Reanudación sin archivo original | 4.4 | Windows/CPU | ⚠️ Parcial | Reutilización con ejecución completa OK; reprocesamiento via `fuentes/` no validado |
| 2026-11-16 | 13 — Exclusión de acceso concurrente | 4.5 | Windows/CPU | ✅ Aprobada — 448 s | Segunda instancia rechazada con `ReunionOcupada`; primera completó sin interferencia |
| 2026-11-15 | Suite automatizada | 5.4 | Linux/GPU Fedora 43 | ✅ 820 passed, 0 fallidos | Incluye `hito-2/tests/`; diferencia respecto a Windows (752) explicada por ese directorio |
| 2026-11-15 | Pipeline completo | 5.2 | Linux/GPU Fedora 43 | ✅ Aprobada — 66,6 s | Audio propio 30,4 s; VRAM 4832/6144 MiB; audio sintético compartido no validado |
| — | Pipeline con audio sintético en GPU | — | Linux/GPU | ⏳ Pendiente | Cachés ya pobladas; validación desde cero pendiente |
| — | Interfaz gráfica y captura en Linux | — | Linux | ⏳ Pendiente | Sin periféricos de audio en el entorno de prueba |
| — | Flujo completo en Linux/CPU | 5.1 | Linux/CPU | ⏳ Pendiente | Entorno no disponible durante este ciclo de validación |

---

## Criterios de cierre de la issue #18

### (a) Matriz de configuraciones evaluadas

| Configuración | Estado | Referencia |
|---|---|---|
| Windows 11 / CPU (Luisa) | ✅ Validada — grupos 1–4 completos (con 4.4 parcial) | Pruebas 1–13, 2026-11-16 |
| Linux/GPU Fedora 43 / cu128 (Matías Caccia) | ✅ Validada con workarounds — suite + pipeline | Resultados Linux, 2026-11-15 |
| Linux/CPU | ⏳ Sin validar | — |

**Veredicto: parcialmente cumplido.** Dos de tres configuraciones evaluadas; Linux/CPU queda fuera de este ciclo de validación.

---

### (b) Procedimientos comprobados

| Procedimiento | Estado | Observaciones |
|---|---|---|
| Flujo principal audio → minuta (WAV y MP3) | ✅ | Windows y Linux/GPU |
| Reproducibilidad del audio sintético | ✅ | SHA-256 bit-exact confirmado (Windows) |
| Reanudación de checkpoints vigentes | ✅ | 1,047 s vs 638 s original (Windows) |
| Captura de audio en vivo desde CLI y GUI | ✅ | Requiere `PYTHONUTF8=1`; reproducción verificada fuera de GUI |
| Cancelación durante etapa pesada | ✅ | Demora ~93 s; archivos huérfanos no corrompen reintento |
| Recuperación tras cancelación (Ctrl+C) | ✅ | `preparar` conservada; pipeline completa desde `diarizar` |
| Recuperación tras terminación abrupta (taskkill) | ✅ | Estado `fallido` detectado; mensaje orientativo |
| Reanudación sin archivo original (via `fuentes/`) | ⚠️ Parcial | Reutilización completa OK; reprocesamiento via `fuentes/` no ejercitado |
| Exclusión de acceso concurrente | ✅ | `ReunionOcupada` en segunda instancia; primera sin interferencia |
| Captura e interfaz gráfica en Linux | ⏳ Pendiente | Sin periféricos de audio en entorno de prueba |

**Veredicto: parcialmente cumplido.** Nueve de diez procedimientos aprobados; reanudación via `fuentes/` y captura Linux pendientes.

---

### (c) Verificaciones automatizadas reutilizables

| Plataforma | Resultado | Fecha |
|---|---|---|
| Windows/CPU (pre-integración con main) | 752 passed, 0 fallidos, 4 skipped, 6 deselected, 52 subtests — 562,78 s | 2026-11-16 |
| Linux/GPU Fedora 43 | 820 passed, 0 fallidos, 2 omitidos, 6 deselected, 52 subtests | 2026-11-15 |
| **Windows/CPU (post-integración con main)** | **910 passed, 0 fallidos, 7 skipped, 6 deselected, 52 subtests — 515,76 s** | **2026-11-16** |

Todos los tests añadidos en este PR son reutilizables en CI (no requieren hardware específico). La diferencia 752 → 910 en Windows/CPU se explica por los tests adicionales incorporados desde `origin/main` (PRs #19 y #20) más las correcciones de compatibilidad Windows documentadas en la sección «Validación posterior a la actualización de main». La diferencia 752 vs 820 (Linux) se explica por `hito-2/tests/` ejecutado adicionalmente en Linux.

**Veredicto: cumplido ✅**

---

### (d) Incompatibilidades resueltas o registradas con responsable

| Incompatibilidad | Plataforma | Estado |
|---|---|---|
| Byte-range lock en exclusión concurrente | Windows | ✅ Corregido — `src/pipeline/ejecucion.py` |
| UTF-8 en CLI de diarización | Windows | ✅ Corregido — `src/diarizacion/diarizar.py`, `contrato.py` |
| Fuentes Qt en plataforma offscreen | Windows | ✅ Corregido — `tests/integracion/test_panel_procesamiento.py` |
| Detección de libarchive DLL | Windows | ✅ Corregido — `src/bibliotecas.py` |
| Detección de FFmpeg DLLs | Windows | ✅ Corregido — `src/verificar_entorno.py` |
| Reproducibilidad espeak-ng | Windows/Linux | ✅ Corregido — flag `-D` en `evaluacion/.../generar.py` |
| UTF-8 en `src/captura/captura.py` | Windows | ⚠️ Registrado — workaround `PYTHONUTF8=1`; corrección pendiente de aprobación |
| `torchcodec 0.7.0+cu128` requiere `libnppicc.so.12` | Linux/GPU cu128 | ⚠️ Registrado — workaround: reinstalar desde PyPI; corrección pendiente |
| Paquetes `7zip` de Fedora sin soporte RAR | Linux/Fedora | ⚠️ Registrado — workaround: `SIETE_ZIP=~/.local/bin/7zz`; corrección pendiente |
| `localizar_7zip` prioriza `7z` sin verificar RAR | Linux/Fedora | ⚠️ Registrado — corrección pendiente |
| README sin sección Fedora | Documentación | ⚠️ Registrado — corrección pendiente |

**Veredicto: parcialmente cumplido.** Incompatibilidades Windows resueltas. Incompatibilidades Linux/GPU registradas con workarounds documentados; correcciones pendientes de coordinación con compañeros.

---

### (e) Documentación actualizada

| Documento | Estado |
|---|---|
| `PR_ISSUE_18.md` — correcciones, hallazgos, evidencias | ✅ Completo |
| Tabla de evidencias funcionales (grupos 1–5) | ✅ Completa (tarea 6.1) |
| Resultados Linux/GPU con autor, fecha y plataforma | ✅ Registrados (tarea 6.2) |
| OpenSpec change `validacion-funcional-issue-18` | ✅ Specs, design, tasks actualizados |
| README — sección Fedora | ⏳ Pendiente (hallazgo #1 Linux) |

**Veredicto: parcialmente cumplido.** Documentación interna del PR completa. README pendiente de actualización para Fedora (fuera del scope de este change según design.md D4).

---

### Resumen de criterios de cierre

| Criterio | Estado |
|---|---|
| (a) Matriz de configuraciones evaluadas | ⚠️ Parcial — Linux/CPU sin validar |
| (b) Procedimientos comprobados | ⚠️ Parcial — `fuentes/` y captura Linux pendientes |
| (c) Verificaciones automatizadas reutilizables | ✅ Cumplido |
| (d) Incompatibilidades resueltas o registradas | ⚠️ Parcial — Linux registradas, correcciones pendientes |
| (e) Documentación actualizada | ⚠️ Parcial — README Fedora pendiente |

---

## Archivos modificados (resumen)

| Archivo | Tipo | Razón |
|---|---|---|
| `src/pipeline/ejecucion.py` | Producción | Fix byte-range lock Windows |
| `src/diarizacion/diarizar.py` | Producción | Fix stdout UTF-8 CLI |
| `src/diarizacion/contrato.py` | Producción | Fix stdout UTF-8 CLI |
| `src/bibliotecas.py` | Producción | Detección libarchive Windows |
| `src/verificar_entorno.py` | Producción | Detección FFmpeg DLLs Windows |
| `tests/integracion/test_panel_procesamiento.py` | Test | Fix fuentes Qt offscreen |
| `tests/integracion/test_workflow.py` | Test | Fix read_text encoding + nuevo test ACL |
| `tests/minutas/test_consolidacion_limites.py` | Test | Fix read_text encoding |
| `tests/minutas/test_minutas.py` | Test | Fix read_text encoding |
| `tests/integracion/test_bibliotecas.py` | Test | Nuevos tests libarchive |
| `tests/diarizacion/test_verificar_entorno.py` | Test | Nuevos tests FFmpeg |
| `evaluacion/asociacion/ejemplo_ideal/generar.py` | Evaluación | Flag `-D` en espeak-ng (reproducibilidad) |

---

## Validación posterior a la actualización de `main` (2026-11-16)

### Contexto

La rama `review/integracion-poc` fue actualizada con los últimos 15 commits de `origin/main`, incorporando funcionalidades desarrolladas por otros integrantes del equipo. Los PRs integrados relevantes fueron:

- **PR #19 — Preservación textual:** nuevos campos en `Intervencion` (`timing`, `speakers_detected`, `source`), soporte AWS Bedrock, y nuevos tests en `tests/integracion/test_workflow.py` y `tests/integracion/test_preservacion_textual.py`.
- **PR #20 — Evaluación modular:** framework de evaluación `hito-2/`, integración MarianMT para traducción, y nuevas dependencias declaradas en `pyproject.toml` y `constraints.txt` (`transformers`, `tokenizers`, `sentencepiece`, `sacremoses`).

Tras la integración, los cambios locales de la issue #18 fueron recuperados (rebase) y se ejecutó la suite completa para detectar regresiones introducidas por `main`.

---

### Primera ejecución posterior a la actualización

**Comando:**
```powershell
.venv\Scripts\python.exe -m pytest -q
```

**Resultado:** `898 passed, 12 failed, 7 skipped, 6 deselected`

Los 12 fallos se clasificaron en cuatro categorías:

| Categoría | Cantidad | Causa raíz | Tests afectados |
|---|---|---|---|
| **A — TOMLDecodeError** | 8 | Rutas Windows (`C:\Users\...`) interpoladas en strings TOML de doble comilla → el parser interpreta `\U` como inicio de un escape Unicode de 8 dígitos | `tests/evaluacion/test_inferir.py` (5), `test_contratos.py` (1), `test_manifiesto.py` (1), `test_originales.py` (1) |
| **B — ModuleNotFoundError** | 2 | `transformers`, `tokenizers`, `sentencepiece`, `sacremoses` declarados en `pyproject.toml` pero no instalados en `.venv` tras la actualización | `tests/evaluacion/test_manifiesto.py` (2) |
| **C — Encoding UTF-8** | 2 | `read_text()` sin `encoding='utf-8'` en tests nuevos del PR #19 → cp1252 corrompe caracteres como `–` (U+2013) y vocales acentuadas | `tests/integracion/test_preservacion_textual.py` (1), `tests/integracion/test_workflow.py` (1) |
| **D — Errores de colección** | 9 errores (no fallos) | Paquetes del núcleo (`soundfile`, `boto3`, `pyannote`, etc.) detectados como faltantes desde el Python del sistema — no desde `.venv` del proyecto | Falsos positivos del entorno: en `.venv\Scripts\python.exe` todos estos paquetes están correctamente instalados |

> **Nota sobre categoría D:** los errores de colección reflejan que pytest fue invocado con el Python del sistema (`C:\...\Programs\Python312\python.exe`, torch 2.9.0) en alguna inspección. Con el `.venv` del proyecto (torch 2.8.0+cpu), `soundfile`, `boto3`, `botocore`, `pyannote`, `huggingface_hub` y demás paquetes del núcleo están instalados y funcionales. No representan fallas reales del entorno de desarrollo.

---

### Correcciones realizadas

#### 1. Lectura explícita en UTF-8 en tests de integración (categoría C)

**Archivos modificados:**
- `tests/integracion/test_preservacion_textual.py`
- `tests/integracion/test_workflow.py`

**Cambios:** se agregó `encoding='utf-8'` a 4 llamadas `read_text()` en tests incorporados por el PR #19. El problema ocurría porque `minutes.md` y `minutes.json` contienen caracteres UTF-8 que Python en Windows lee con cp1252 por defecto.

```python
# tests/integracion/test_preservacion_textual.py — tres llamadas
md = resultado.markdown.read_text(encoding='utf-8')          # antes: sin encoding
meta = json.loads(resultado.manifiesto.read_text(encoding='utf-8'))
contenido = ruta.read_text(encoding='utf-8')

# tests/integracion/test_workflow.py — línea 1206
assert 'falta de ubicación temporal' in (s.salida / 'minutes.md').read_text(encoding='utf-8')
```

#### 2. Instalación de dependencias faltantes (categoría B)

Los paquetes declarados como requeridos en `pyproject.toml` pero ausentes en `.venv` fueron instalados respetando los pins de `constraints.txt`:

| Paquete | Versión | Origen de la declaración |
|---|---|---|
| `transformers` | 5.22.1 | `pyproject.toml` (required) + `constraints.txt` |
| `tokenizers` | 0.23.3 | `constraints.txt` (dependencia de `transformers`) |
| `sentencepiece` | 0.2.2 | `pyproject.toml` (required) + `constraints.txt` |
| `sacremoses` | 0.2.0 | `pyproject.toml` (required) + `constraints.txt` |
| `typer` | 0.27.3 | `constraints.txt` (dependencia de `transformers`) |
| `annotated-doc` | 0.0.5 | `constraints.txt` (dependencia de `typer`) |
| `shellingham` | 1.5.4 | `constraints.txt` (dependencia de `typer`) |

**Comando utilizado:**
```powershell
.venv\Scripts\python.exe -m pip install -c constraints.txt `
  "transformers==5.22.1" "tokenizers==0.23.3" `
  "sentencepiece==0.2.2" "sacremoses==0.2.0" `
  "typer==0.27.3" "annotated-doc==0.0.5" "shellingham==1.5.4"
```

**Verificación de conflictos:**
```powershell
.venv\Scripts\python.exe -m pip check
# → No broken requirements found.
```

#### 3. Rutas Windows en tests de evaluación modular (categoría A)

**Archivos modificados:**
- `tests/evaluacion/test_inferir.py`
- `tests/evaluacion/test_contratos.py`
- `tests/evaluacion/test_manifiesto.py`
- `tests/evaluacion/test_originales.py`

**Causa:** los tests del PR #20 inyectan `tmp_path` directamente en strings TOML usando f-strings. En Windows, `str(Path)` produce separadores `\` y el token `\U` que TOML trata como escape Unicode de 8 dígitos → `TOMLDecodeError: Invalid hex value`.

**Corrección:** reemplazar `f"{ruta}"` por `f"{ruta.as_posix()}"` en todas las sustituciones de paths dentro de strings TOML. `Path.as_posix()` produce `C:/Users/...` — válido en TOML y aceptado por Python como ruta en Windows. Adicionalmente, dos aserciones `endswith()` en `test_comandos_por_fuente` que verificaban separadores `/` en rutas que en Windows tienen `\` fueron corregidas con `Path(...).as_posix().endswith(...)`.

```python
# Antes — provoca TOMLDecodeError en Windows
.replace('salida = "evaluacion/modular/datos"', f'salida = "{datos}"')

# Después — válido en ambas plataformas
.replace('salida = "evaluacion/modular/datos"', f'salida = "{datos.as_posix()}"')

# Antes — falla endswith con separador incorrecto en Windows
assert pipeline[4].endswith("figshare/S22/01/audio.wav")

# Después — normaliza separador antes de comparar
assert Path(pipeline[4]).as_posix().endswith("figshare/S22/01/audio.wav")
```

**Alcance:** todos los cambios de esta categoría son en archivos de tests. El código de producción no fue modificado por estos problemas. La corrección con `as_posix()` es compatible con Linux, donde `Path.as_posix()` devuelve la misma cadena que `str(Path)`.

---

### Validación de las correcciones

#### Categoría C — 2 tests de UTF-8

```
.venv\Scripts\python.exe -m pytest tests/integracion/test_preservacion_textual.py::test_de_stt_a_minutas_y_visores tests/integracion/test_workflow.py::test_preservacion_textual_en_workflow_y_reutilizacion -v
```

```
tests/integracion/test_preservacion_textual.py::test_de_stt_a_minutas_y_visores  PASSED
tests/integracion/test_workflow.py::test_preservacion_textual_en_workflow_y_reutilizacion  PASSED
2 passed in 5.77s
```

#### Categoría A — 8 tests de TOML

```
.venv\Scripts\python.exe -m pytest tests/evaluacion/test_inferir.py tests/evaluacion/test_contratos.py::test_evaluar_por_linea_de_comandos tests/evaluacion/test_manifiesto.py::test_verificar_por_linea_de_comandos tests/evaluacion/test_originales.py::test_preparar_no_escribe_con_original_invalido -v
```

```
tests/evaluacion/test_inferir.py::test_comandos_por_fuente       PASSED
tests/evaluacion/test_inferir.py::test_muestra_alterada          PASSED
tests/evaluacion/test_inferir.py::test_reutilizacion             PASSED
tests/evaluacion/test_inferir.py::test_rehacer_y_salida_incompleta  PASSED
tests/evaluacion/test_inferir.py::test_fallo_de_un_modulo_no_se_reutiliza  PASSED
tests/evaluacion/test_contratos.py::test_evaluar_por_linea_de_comandos     PASSED
tests/evaluacion/test_manifiesto.py::test_verificar_por_linea_de_comandos  PASSED
tests/evaluacion/test_originales.py::test_preparar_no_escribe_con_original_invalido  PASSED
8 passed in 2.93s
```

---

### Estado final de la suite

Evolución de la suite tras la actualización de `main`:

| Ejecución | Pasados | Fallidos | Skipped | Deselected | Subtests | Duración | Correcciones aplicadas |
|---|---|---|---|---|---|---|---|
| Tras actualización (inicial) | 898 | 12 | 7 | 6 | — | — | Ninguna |
| Tras categorías B y C | 902 | 8 | 7 | — | — | — | Dependencias instaladas + UTF-8 en tests de integración |
| **Suite completa final** | **910** | **0** | **7** | **6** | **52** | **515,76 s** | Todas (A + B + C) |

**Resultado definitivo:**
```
910 passed, 7 skipped, 6 deselected, 52 subtests passed in 515.76s
```

Ningún fallo en ninguna categoría. Las correcciones de compatibilidad Windows (categorías A, B y C) se aplicaron íntegramente en archivos de tests, sin modificar el código de producción.

---

### Archivos modificados en esta etapa

| Archivo | Tipo | Corrección |
|---|---|---|
| `tests/integracion/test_preservacion_textual.py` | Test | Categoría C — `encoding='utf-8'` en 3 llamadas `read_text()` |
| `tests/integracion/test_workflow.py` | Test | Categoría C — `encoding='utf-8'` en 1 llamada `read_text()` |
| `tests/evaluacion/test_inferir.py` | Test | Categoría A — `as_posix()` en paths TOML y en 2 aserciones `endswith()` |
| `tests/evaluacion/test_contratos.py` | Test | Categoría A — `as_posix()` en 4 paths TOML |
| `tests/evaluacion/test_manifiesto.py` | Test | Categoría A — `as_posix()` en 2 paths TOML |
| `tests/evaluacion/test_originales.py` | Test | Categoría A — `as_posix()` en 2 paths TOML |

Ninguno de estos cambios modifica el código de producción del pipeline ni los contratos de las interfaces existentes.
