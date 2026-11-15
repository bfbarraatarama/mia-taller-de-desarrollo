# Registro de desarrollo de diarización

Estado histórico al 09/11/2026, previo a la integración. Las tareas, mediciones y limitaciones se conservan como evidencia de origen; no constituyen el backlog vigente ni una certificación de la aplicación integrada. Véanse la [guía actual](../../docs/diarizacion/README.md), los [procedimientos de evaluación](README.md) y la [validación de integración](../../docs/validacion-integracion.md).

> **Estado (09/11/2026).** Las tareas están en [`docs/diarizacion/openspec/changes/etapa-2-diarizacion/tasks.md`](../../docs/diarizacion/openspec/changes/etapa-2-diarizacion/tasks.md).
> - **Hecho:**
>   - el módulo y las pruebas de nivel 1;
>   - la integración con la Etapa 1 (nivel 2, en CPU);
>   - la preparación del dataset de Figshare (S26, 25 grabaciones);
>   - la evaluación de calidad **en CPU**, reproducible con los JSON versionados: DER estricto 23,15 %, DER NIST 12,32 % y JER 40,02 %. Ver [`evaluacion/diarizacion/EVALUACION_S26.md`](EVALUACION_S26.md);
>   - la misma evaluación **en GPU (CUDA)**, informada por una compañera desde su equipo, con las mismas métricas globales (tarea 7.7). Sus archivos no están en el repositorio (ver [Pruebas en GPU](#pruebas-en-gpu-tareas-73-74-y-77)).
> - **Pendiente:**
>   - **7.3:** el test automatizado de CUDA (`tests/diarizacion/test_evaluacion_gpu.py`). La memoria se midió solo a mano.
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
| Python | 3.12.x (verificado 3.12.10) | `src/verificar_entorno.py` |
| PyTorch / torchaudio | 2.8.0 (`+cpu` o `+cu128`) | comando de instalación + `constraints.txt` |
| TorchCodec | 0.7.0 (serie 0.7, la de torch 2.8; carga FFmpeg **4 a 7**) | archivos de dependencias de la raíz |
| pyannote.audio | 4.0.7 | archivos de dependencias de la raíz |
| pyannote.metrics | 4.2.0 | archivos de dependencias de la raíz |
| Resto del árbol integrado | restricciones comunes | [`constraints.txt`](../../constraints.txt) |
| FFmpeg | 7.1.1 *shared* (gyan.dev, Windows) | instalación local (véase la guía vigente) |
| 7-Zip | 22.01 o posterior | solo para el dataset de Figshare (grupo 6) |

Las versiones y perfiles se definen en `pyproject.toml` y `constraints.txt` de la raíz; el procedimiento general instala también el resto del proyecto.

### Verificación básica del nivel 2 (tarea 5.5)

Verificación **automática** sobre las tres grabaciones de `resultados/grabaciones/nivel2/`. Los datos salen de `evaluacion/diarizacion/reportes/integracion_*.json` y de los `diarization.json` de `nivel2/<nombre>/`. No hay revisión auditiva obligatoria.

**Evidencia versionada:** [`evaluacion/diarizacion/resultados/nivel2/`](resultados/nivel2/) guarda copias de los tres reportes, `integracion_<grabacion>.json`. Cada uno tiene:
- la grabación, el estado de la Etapa 1, la duración y el dispositivo;
- el `tiempo_s`, los hablantes y los segmentos (corregidos y descartados);
- por hablante, la cantidad de segmentos, el tiempo de habla y los primeros segmentos.

No tienen audio ni rutas locales, y se revisó que no incluyan datos personales. `evaluacion/diarizacion/reportes/` sigue fuera de git; estas copias se hacen a mano.

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

## Qué corre sin GPU y qué en el equipo con GPU

| Qué | Sin GPU (máquina de desarrollo) | Con GPU NVIDIA |
|---|---|---|
| Instalación (archivos de dependencias de la raíz) | PyTorch `2.8.0+cpu` | PyTorch `2.8.0+cu128` |
| `src/verificar_entorno.py` | sí | sí, con `--gpu` |
| Nivel 1 (unitarias, sin modelo) | sí | sí |
| Nivel 2 (Etapa 1 → Etapa 2, `-m slow`) | sí (verificado) | sí |
| Preparación y `--verificar` del dataset de Figshare | sí (verificado; no usa el modelo) | sí |
| Nivel 3a, calidad DER/JER (`calidad`, tareas 7.2, 7.6 y 7.7) | sí (verificado: S26 completo, 2333,6 s de inferencia) | sí (informado por una compañera: S26 completo en CUDA, 79,1 s de inferencia) |
| Nivel 3b, pruebas de CUDA (`gpu`, tarea 7.3: memoria, `dispositivo: cuda`, CPU vs GPU) | no (se saltean) | **pendiente**: el test todavía no existe |

### Pruebas en GPU (tareas 7.3, 7.4 y 7.7)

La máquina de desarrollo de la Etapa 2 solo tiene CPU. Las pruebas en GPU las hizo **una compañera en su equipo** y las informó en su revisión del PR #8. **Sus archivos (reportes de calidad, hipótesis y salida de `verificar_entorno.py`) no están en el repositorio**, así que estos valores son evidencia informada, no reproducible desde los JSON versionados. El detalle está en [`registro-pruebas.md`](../../docs/diarizacion/openspec/changes/etapa-2-diarizacion/registro-pruebas.md), sección "Pruebas en GPU".

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
- **7.3:** escribir `tests/diarizacion/test_evaluacion_gpu.py` (marker `gpu`). Debe medir la memoria de CUDA de forma **automatizada** (la medición de arriba fue manual), comprobar `dispositivo: "cuda"` y la compatibilidad funcional CPU/GPU sobre la primera grabación válida, y escribir `evaluacion/diarizacion/reportes/gpu_S26.json`.
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
