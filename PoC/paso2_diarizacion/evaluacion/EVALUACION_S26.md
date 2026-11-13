# Evaluación de calidad de la diarización: UBA Games, sesión S26

Este documento reúne la metodología y los resultados de la evaluación de la Etapa 2 sobre las 25 grabaciones de la sesión S26 de UBA Games (Figshare v2). Hay dos corridas:

| Corrida | Fecha y equipo | Origen de las cifras | ¿Reproducible desde el repo? |
|---|---|---|---|
| **CPU** (principal de este documento) | 08/11/2026, máquina de desarrollo de la Etapa 2 (Windows 11) | `evaluacion/resultados/calidad_S26.json`, `calidad_total.json`, `hipotesis_S26/*.json` y `evaluacion/figshare_test.manifest.json`, todos versionados | **Sí**: `pytest -k resultados_publicados` recalcula las métricas sin el modelo |
| **GPU (CUDA)** | informada el 09/11/2026 por **una compañera**, desde su equipo (Ubuntu 24.04, RTX 4060 Ti) | su informe, transcripto en `openspec/changes/etapa-2-diarizacion/registro-pruebas.md` | **No**: sus reportes y sus hipótesis no están en el repositorio |

Salvo donde se indique GPU, todas las cifras son de la corrida en CPU.

> **Alcance.** Los valores son una **línea de base** de la PoC, sin umbral de aceptación. Las 25 grabaciones son de **una misma sesión**, con los mismos dos participantes y el mismo juego. No representan otras voces, otros micrófonos ni reuniones (ver [Limitaciones](#limitaciones)).

## Objetivo

Medir qué tan bien `pyannote/speaker-diarization-community-1`, tal como lo usa la Etapa 2, responde **quién habla y cuándo** sobre audio con dos hablantes y una referencia anotada. El modelo recibe el mismo tipo de entrada que le da la Etapa 1: un WAV mono de 16 kHz y PCM16.

## Dataset

| | |
|---|---|
| Fuente | UBA Games, Figshare `22647313` versión 2, licencia CC BY 4.0. Se usan los RAR ya descargados por el Hito 2 (`hito-2/.cache/uba_games/figshare-v2/`) |
| Sesión | S26, tareas `s26.objects.01` a `s26.objects.25` |
| Audio | `wavs/Sin separar canales/S26_falta_separar_canales/s26.objects.TT.wav`: estéreo, 16 kHz, PCM16, un participante por canal |
| Referencia | `phrases/S26/s26.objects.TT.channel1.phrases` y `.channel2.phrases`: frases transcritas por canal (`inicio`, `fin`, `texto`) |
| Total | 25 grabaciones, 1821,2 s de audio (30,4 min), 1457,6 s de habla de referencia, 151,9 s de habla superpuesta |

La integridad se verifica sin extraer ni modificar nada:
- los RAR, contra `hito-2/fuentes.toml` (bytes y MD5) y `fuentes.lock.json` (SHA-256);
- cada archivo usado de `extraidos/`, contra el listado del RAR (tamaño y CRC32, con `7z l -slt`), y además se registra su SHA-256.

## Preparación (`evaluacion/preparar_figshare.py --preparar`)

1. **Validez de cada grabación:**
   - WAV completo estéreo, de 16 kHz y PCM16, leído completo;
   - anotaciones bien formadas, con los criterios del Hito 2;
   - exceso terminal de 0,01 s o menos (`TOLERANCIA_FIN_FIGSHARE_S`, importada de `hito-2/scripts/validar_muestra.py`);
   - correspondencia canal ↔ hablante: cada canal se correlaciona más con su `wavs/S26/…channelN.wav` que con el otro.

   **Resultado:** las 25 son válidas y no se excluyó ninguna. La correlación de cada canal con su WAV separado es de 0,99988 o más, y con el otro canal es de 0,114 o menos. El exceso terminal máximo es 0,00975 s.
2. **WAV mono:** `int16(floor_divide(int32(L) + int32(R), 2))`, la fórmula del Hito 2, con los mismos cuadros. Es lo que recibe pyannote.
3. **Referencia RTTM:**
   - hablantes `figshare_v2_S26_canal1` y `figshare_v2_S26_canal2`;
   - `#` (silencio marcado) se excluye y el texto con letras es habla;
   - los intervalos del mismo canal superpuestos o contiguos se unen (4 uniones en total);
   - **el solapamiento entre canales se conserva**;
   - los fines que superan la duración real en 0,01 s o menos se ajustan a esa duración (2 ajustes, registrados con el fin original);
   - los tiempos tienen 3 decimales y nunca superan la duración real.

   En total son 1031 segmentos de referencia.
4. **Indicador de cobertura** (solo indicio, no cambia la referencia): compara la energía de cada canal con lo anotado.
   - **Posible habla sin anotar:** 2,78 s en total, en 6 de los 50 canales. El máximo es 0,93 s, en el canal 2 de la tarea 20.
   - **Habla anotada con energía baja:** entre el 3,6 % y el 30,4 % de las ventanas, según el canal. Probablemente son pausas dentro de las frases, pero no se revisaron a mano.
5. **Manifiesto** (`evaluacion/figshare_test.manifest.json`):
   - `contenido` es determinista e incluye los SHA-256 de cada WAV mono y RTTM; su hash es `contenido_sha256 = 47bfcccc5190d7f556d349648a4f26c7265d46015435e5933bba4afd7bfd4a7e`;
   - `ejecucion` es variable y no se compara.

### Decisiones tomadas al ampliar a S26 completo (08/11/2026)

| Decisión | Motivo | Efecto |
|---|---|---|
| Se admite **1 cuadro de más al final** en los WAV separados (`TOLERANCIA_CUADROS_SEPARADO = 1`) | En 9 tareas (06, 07, 10, 11, 14, 15, 17, 20 y 24), los dos `channelN.wav` tienen 1 cuadro más que el completo. Comparados desde el inicio, la correlación es de 0,9999 con su canal; con 1 cuadro de desfase baja a 0,89–0,95, así que el cuadro sobrante está al final | Solo afecta la comprobación de la correspondencia, que se calcula sobre los cuadros en común. El manifiesto registra `diferencia_cuadros`. **No cambia ni la entrada del modelo ni la referencia.** Cualquier otra diferencia sigue excluyendo la grabación |
| `-?` y `?-` se clasifican como **`habla`** en `politica_etiquetas.json` | Son 3 intervalos sin letras, todos en el canal 2: `-?` en las tareas 09 (0,135 s) y 18 (0,031 s), y `?-` en la 12 (0,084 s). Parecen vocalizaciones breves sin transcribir | Suman 0,25 s de referencia. El cambio de política queda reflejado en `politica_etiquetas_sha256` del manifiesto |

## Ejecución del modelo

| | |
|---|---|
| Modelo | `pyannote/speaker-diarization-community-1`, con pyannote.audio 4.0.7, torch 2.8.0+cpu y Python 3.12.10 |
| Dispositivo | `device="auto"`, que en la máquina de desarrollo, sin GPU, resolvió **CPU**. En el equipo de la compañera resolvió **CUDA** (ver [Resultados en GPU](#resultados-en-gpu-informados-por-una-compañera)) |
| Cantidad de hablantes | **detección automática** (`num_speakers` sin fijar). La corrida diagnóstica con `num_speakers=2` **no se ejecutó** |
| Salida | `diarization.json` de la Etapa 2, normalizado y validado con `contrato.py` en las 25 grabaciones |
| Reutilización | `s26.objects.04` reutilizó su corrida anterior, que es compatible: mismo SHA-256 del WAV mono, modelo, versiones, `num_speakers` y dispositivo |
| Tiempo (CPU) | 2260,4 s (37,7 min) de inferencia nueva para 24 grabaciones, más 73,1 s de la 04. Son 2333,6 s para 1821,2 s de audio, unos 1,28 s de cómputo por segundo de audio |
| Tiempo (GPU, informado) | 79,146 s para 1821,246 s de audio, las 25 grabaciones sin reutilizar: unas 23 veces más rápido que el tiempo real |

## Métricas

Las tres métricas son de `pyannote.metrics` 4.2.0, **incluyen el habla superpuesta** (`skip_overlap=False`) y evalúan la región `[0, duración]` de cada grabación.

| Métrica | Definición |
|---|---|
| `der_estricto` | `DiarizationErrorRate(collar=0.0)`: cada borde cuenta |
| `der_tolerancia` | **DER de pyannote.metrics con tolerancia NIST** de ±0,25 s por borde (`collar=0.5`, porque en pyannote el collar es el ancho total). No es un resultado de `md-eval` |
| `jer` | `JaccardErrorRate(collar=0.0)`: promedio del error de cada hablante de la referencia, con el mismo peso para todos |

- **DER global:** suma de los componentes de todas las grabaciones dividida por la suma del habla de referencia, es decir, ponderado por el tiempo.
- **JER global:** media del error de los 50 hablantes de referencia.
- **Estadísticos por grabación** (media, mediana, cuartiles, mínimo, máximo y desviación estándar muestral): calculados sin ponderar.

## Resultados globales

| Métrica | Valor global | Falsa alarma | Habla perdida | Confusión | Habla de referencia evaluada |
|---|---|---|---|---|---|
| DER estricto | **23,15 %** | 116,16 s (7,2 %) | 60,25 s (3,7 %) | 196,15 s (12,2 %) | 1609,5 s |
| DER NIST (±0,25 s) | **12,32 %** | 3,54 s (0,4 %) | 17,20 s (1,8 %) | 97,23 s (10,2 %) | 957,7 s (59,5 %) |
| JER | **40,02 %** | | | | |

El habla de referencia evaluada (1609,5 s) es mayor que los 1457,6 s de habla, porque el habla superpuesta cuenta una vez por cada hablante.

**Cantidad de hablantes:** coincide en 24 de 25 grabaciones (96 %). En la tarea 02 se detectó 1 hablante en lugar de 2.

### Resultados en GPU (informados por una compañera)

> **Evidencia informada, no versionada.** Una compañera del equipo repitió la evaluación con `pytest -m calidad` en su equipo y la informó en su revisión del PR #8. Sus `calidad_*.json`, sus hipótesis y la salida de `verificar_entorno.py` **no están en el repositorio**: estos valores no se pueden recalcular desde los JSON versionados, que son los de CPU.

| | CPU (versionado) | GPU (informado) |
|---|---|---|
| Equipo | Windows 11, Python 3.12.10, `torch 2.8.0+cpu` | Ubuntu 24.04, Python 3.12.3, RTX 4060 Ti 16 GB, `torch 2.8.0+cu128`, pyannote.audio 4.0.7 |
| Grabaciones | 25/25 (la 04 reutilizada de una corrida compatible) | 25/25 en CUDA, sin reutilizar |
| WAV mono y RTTM | coinciden con el manifiesto | coinciden con el manifiesto publicado |
| DER estricto | 23,15 % | 23,15 % |
| DER NIST (±0,25 s) | 12,32 % | 12,32 % |
| JER | 40,02 % | 40,02 % |
| Cantidad de hablantes correcta | 24/25 | 24/25 |
| Tiempo de inferencia | 2333,6 s | 79,146 s |

- **Comparación:** las métricas globales coinciden con 2 decimales. Las métricas por grabación y las hipótesis segmento a segmento **no se compararon**, porque las de GPU no están disponibles. Coincidir en lo global no prueba que las salidas sean idénticas.
- **Memoria, medición manual de la compañera sobre un WAV de 30 s:**
  - 2 hablantes, 13 segmentos y 0 violaciones del contrato;
  - pico de memoria asignada de 1628,5 MiB;
  - incremento residual de 8,12 MiB después de `diarizar()`, por debajo del límite de 64 MiB.

  El test automatizado de memoria (tarea 7.3) todavía no existe.
- **Advertencias no bloqueantes informadas:** TF32 y `std(): degrees of freedom is <= 0`; esta última también aparece en CPU.

### Dispersión por grabación (sin ponderar)

| Métrica | Media | Mediana | Q1 – Q3 | Mínimo | Máximo | Desv. estándar |
|---|---|---|---|---|---|---|
| DER estricto | 23,1 % | 23,4 % | 17,4 – 28,4 % | 12,7 % (13) | 34,4 % (07) | 6,9 p.p. |
| DER NIST | 11,9 % | 12,0 % | 6,6 – 17,2 % | 0,0 % (06) | 28,7 % (17) | 8,0 p.p. |
| JER | 40,0 % | 44,9 % | 33,0 – 48,8 % | 15,1 % (22) | 64,4 % (02) | 12,7 p.p. |

## Resultados por grabación

Ordenados por DER estricto. FA = falsa alarma.
- **Componentes:** las columnas FA, perdida y confusión son del DER estricto, en segundos.
- **"Evaluado NIST":** habla de referencia que queda dentro de la evaluación con la tolerancia NIST.
- **Columnas de solapamiento:** DER estricto calculado dentro y fuera de las regiones donde la referencia tiene 2 hablantes a la vez.

| # | Tarea | Duración (s) | Habla ref. (s) | Superpuesta (s) | Hablantes det. | DER estricto | FA (s) | Perdida (s) | Confusión (s) | DER NIST | Confusión NIST (s) | Evaluado NIST | JER | DER con solap. | DER sin solap. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 13 | 52,9 | 42,9 | 1,1 | 2 | 12,7 % | 3,83 | 0,11 | 1,67 | 0,4 % | 0,12 | 64,9 % | 35,6 % | 3,4 % | 13,2 % |
| 2 | 22 | 73,9 | 53,8 | 2,9 | 2 | 12,9 % | 3,83 | 2,47 | 1,02 | 1,9 % | 0,00 | 63,7 % | 15,1 % | 16,9 % | 12,5 % |
| 3 | 06 | 31,4 | 19,3 | 0,2 | 2 | 13,5 % | 1,09 | 0,43 | 1,12 | 0,0 % | 0,00 | 70,0 % | 47,2 % | 0,0 % | 13,7 % |
| 4 | 09 | 119,4 | 107,6 | 20,1 | 2 | 16,8 % | 10,51 | 4,71 | 6,21 | 6,2 % | 2,61 | 53,4 % | 19,9 % | 8,1 % | 20,7 % |
| 5 | 19 | 109,8 | 95,3 | 15,1 | 2 | 17,1 % | 7,33 | 3,31 | 8,26 | 5,9 % | 3,48 | 55,7 % | 23,7 % | 8,2 % | 20,5 % |
| 6 | 25 | 107,9 | 85,3 | 5,5 | 2 | 17,3 % | 9,08 | 3,83 | 2,81 | 2,6 % | 0,20 | 61,1 % | 22,5 % | 12,7 % | 18,0 % |
| 7 | 18 | 40,1 | 31,7 | 1,6 | 2 | 17,4 % | 1,36 | 0,65 | 3,79 | 9,0 % | 2,03 | 67,8 % | 46,7 % | 11,4 % | 18,1 % |
| 8 | 10 | 76,7 | 60,3 | 5,1 | 2 | 17,7 % | 2,85 | 2,98 | 5,78 | 7,0 % | 2,07 | 63,0 % | 38,8 % | 10,2 % | 19,1 % |
| 9 | 11 | 32,3 | 28,4 | 3,6 | 2 | 18,1 % | 2,32 | 0,40 | 3,05 | 6,7 % | 1,26 | 64,1 % | 34,4 % | 5,3 % | 21,7 % |
| 10 | 16 | 91,5 | 67,7 | 6,9 | 2 | 18,2 % | 5,39 | 5,95 | 2,27 | 7,3 % | 0,34 | 60,0 % | 20,3 % | 4,1 % | 21,5 % |
| 11 | 14 | 74,9 | 57,5 | 1,9 | 2 | 19,4 % | 3,67 | 0,78 | 7,05 | 6,6 % | 2,42 | 64,0 % | 50,0 % | 11,1 % | 19,9 % |
| 12 | 23 | 107,1 | 85,0 | 11,7 | 2 | 22,2 % | 7,24 | 5,91 | 8,30 | 12,0 % | 4,57 | 56,0 % | 27,2 % | 14,2 % | 24,7 % |
| 13 | 21 | 116,5 | 88,5 | 8,9 | 2 | 23,4 % | 5,02 | 4,74 | 13,02 | 12,6 % | 6,06 | 56,9 % | 47,0 % | 21,8 % | 23,7 % |
| 14 | 01 | 48,5 | 42,5 | 4,5 | 2 | 23,9 % | 3,24 | 0,76 | 7,24 | 18,4 % | 5,04 | 62,1 % | 44,8 % | 8,3 % | 27,7 % |
| 15 | 08 | 29,4 | 21,9 | 1,1 | 2 | 24,9 % | 1,78 | 0,73 | 3,23 | 6,6 % | 0,77 | 63,6 % | 49,7 % | 2,9 % | 27,3 % |
| 16 | 20 | 68,4 | 53,3 | 5,9 | 2 | 24,9 % | 3,56 | 1,22 | 9,99 | 15,8 % | 5,87 | 62,6 % | 45,3 % | 8,0 % | 29,1 % |
| 17 | 05 | 63,2 | 52,5 | 7,9 | 2 | 26,2 % | 4,83 | 2,80 | 8,18 | 13,3 % | 3,67 | 64,2 % | 44,9 % | 16,9 % | 29,5 % |
| 18 | 12 | 95,7 | 73,6 | 5,3 | 2 | 27,2 % | 4,45 | 2,61 | 14,42 | 16,6 % | 7,33 | 57,8 % | 37,1 % | 18,8 % | 28,5 % |
| 19 | 04 | 52,3 | 43,6 | 5,1 | 2 | 28,4 % | 2,80 | 1,44 | 9,59 | 18,2 % | 4,76 | 54,2 % | 49,1 % | 10,6 % | 33,2 % |
| 20 | 03 | 33,9 | 25,1 | 0,9 | 2 | 29,4 % | 3,15 | 1,72 | 2,77 | 14,9 % | 0,92 | 59,9 % | 33,0 % | 18,7 % | 30,2 % |
| 21 | 02 | 35,5 | 25,7 | 0,1 | 1 | 31,2 % | 1,62 | 0,56 | 5,88 | 17,2 % | 2,96 | 68,1 % | 64,4 % | 50,0 % | 31,0 % |
| 22 | 15 | 136,6 | 116,6 | 16,6 | 2 | 31,6 % | 11,74 | 3,11 | 27,25 | 22,4 % | 15,46 | 57,2 % | 47,7 % | 5,0 % | 40,4 % |
| 23 | 17 | 55,8 | 44,9 | 7,1 | 2 | 33,7 % | 3,43 | 0,90 | 13,22 | 28,7 % | 8,81 | 62,9 % | 51,1 % | 2,8 % | 45,3 % |
| 24 | 24 | 114,4 | 92,9 | 8,9 | 2 | 33,9 % | 5,06 | 4,19 | 25,32 | 27,2 % | 14,95 | 54,6 % | 56,2 % | 15,6 % | 37,8 % |
| 25 | 07 | 53,4 | 41,6 | 3,9 | 2 | 34,4 % | 6,97 | 3,96 | 4,70 | 20,1 % | 1,54 | 62,0 % | 48,8 % | 9,0 % | 39,6 % |

La referencia tiene 2 hablantes en las 25 grabaciones.

## Análisis de errores

### Confusión de hablantes
- **Es el componente principal.** Con la tolerancia NIST, 10,2 de los 12,3 puntos de DER son confusión, y en el DER estricto es el mayor componente en 18 de 25 grabaciones.
- **El error se concentra en el hablante con menos habla.** En las **25 grabaciones**, el hablante de referencia con más error de JER es el que tiene menos habla en esa grabación. En promedio, ese hablante tiene un error del 58,7 %, contra el 21,4 % del otro. Es coherente con que el modelo atribuya parte del habla del participante minoritario al mayoritario, y explica por qué el JER (40 %), que da el mismo peso a cada hablante, es mucho mayor que el DER.
- **Dónde se acumula la confusión:** en el DER estricto, las grabaciones con más confusión son la 15 (27,2 s), la 24 (25,3 s), la 12 (14,4 s), la 17 (13,2 s) y la 21 (13,0 s).
- **Tarea 02:** es el único error de cantidad. Se detectó un solo hablante: el canal 1, con 6,1 s de habla, quedó sin pareja (error de JER 1,0) y su habla se atribuyó al hablante del canal 2.

### Con y sin solapamiento

Para separar el error se fija el emparejamiento global de cada grabación y se cuentan los errores en dos regiones disjuntas. Las dos suman exactamente el DER estricto de la grabación, y una prueba de nivel 1 lo verifica.

| Región (DER estricto) | Duración | Habla de referencia | Falsa alarma | Habla perdida | Confusión | DER |
|---|---|---|---|---|---|---|
| **Con solapamiento** (2 hablantes en la referencia) | 151,9 s | 303,9 s | 0,00 s | 31,67 s | 0,00 s | **10,4 %** |
| **Sin solapamiento** (resto de `[0, duración]`) | 1669,3 s | 1305,6 s | 116,16 s | 28,58 s | 196,15 s | **26,1 %** |

- **Con solapamiento**, todo el error es **habla perdida**: el modelo detecta a uno de los dos participantes pero no al segundo.
  - La confusión y la falsa alarma dan 0 por cómo se calculan: con 2 hablantes en la referencia, cualquier etiqueta del sistema emparejada coincide con alguno de los dos.
  - Por eso, en esta región el error solo puede aparecer como habla perdida, o como confusión si hubiera una tercera etiqueta sin pareja.
- **Sin solapamiento** está toda la confusión y la falsa alarma. Es decir, la atribución errónea ocurre cuando habla **una sola persona**, no en el habla superpuesta.

### Bordes y tolerancia NIST
- **La diferencia entre el DER estricto (23,15 %) y el NIST (12,32 %) viene sobre todo de la falsa alarma**, que baja de 116,2 s a 3,5 s. También baja la habla perdida, de 60,2 s a 17,2 s. Son, sobre todo, bordes de frases y pausas cortas que la referencia no marca como habla.
- **Limitación de la tolerancia NIST:** solo evalúa el **59,5 %** del habla de referencia (957,7 de 1609,5 s); por grabación, entre el 53,4 % y el 70,0 %. La referencia tiene muchas frases cortas, y la zona de ±0,25 s alrededor de cada borde queda fuera de la evaluación. Por eso `der_tolerancia` mide sobre un subconjunto del habla y conviene leerlo junto con el estricto. El 0,0 % de la tarea 06 sale de una grabación con 14 segmentos de referencia, de la que se evaluó el 70 %.

## Limitaciones

1. **Representatividad:** una sola sesión (S26), con los mismos dos participantes, el mismo equipo de grabación y el mismo dominio (un juego colaborativo, no reuniones). La dispersión entre grabaciones no refleja la variabilidad entre personas ni entre condiciones.
2. **Referencia:** son frases transcritas por canal, no turnos de habla. Pueden incluir pausas internas y omitir vocalizaciones breves sin transcribir.
3. **Transcripción posiblemente incompleta:** el README de origen indica que S26–S30 vienen de `annotations_incompleto`. El indicador de cobertura no encontró habla sin anotar relevante (2,78 s en total), pero es solo un indicio.
4. **Sin acuerdo entre anotadores** y con **2 hablantes por grabación**: no se evalúa el caso de 3 o más.
5. **La tolerancia NIST** deja afuera el 40,5 % del habla de referencia (ver arriba). `der_tolerancia` no es comparable de forma directa con resultados de `md-eval` ni con DER publicados de otros corpus.
6. **CPU reproducible, GPU solo informada, y solo la corrida principal:**
   - la corrida en GPU de la compañera dio las mismas métricas globales, pero sus archivos no están versionados, así que no se puede verificar grabación por grabación;
   - el test automatizado de memoria de CUDA (tarea 7.3) sigue pendiente;
   - la corrida diagnóstica con `num_speakers=2` no se ejecutó en ningún dispositivo.

## Cómo reproducir

Desde la raíz del repo, con el entorno de la Etapa 2 instalado según el [README](../README.md), con 7-Zip y con los RAR del Hito 2 en `hito-2/.cache/uba_games/figshare-v2/`:

```powershell
$py = "PoC/paso2_diarizacion/.venv/Scripts/python.exe"
$sel = 1..25 | ForEach-Object { '{0:D2}' -f $_ }
& $py -X utf8 PoC/paso2_diarizacion/evaluacion/preparar_figshare.py --preparar --seleccion $sel   # mono, RTTM y manifiesto
& $py -X utf8 PoC/paso2_diarizacion/evaluacion/preparar_figshare.py --verificar                  # mismos SHA-256 que el manifiesto
& $py -X utf8 -m pytest PoC/paso2_diarizacion -m calidad -rs                                    # pyannote y métricas (~39 min en CPU; ~80 s informados en GPU)
& $py -X utf8 PoC/paso2_diarizacion/evaluacion/publicar_resultados.py                           # copia los reportes a evaluacion/resultados/
```

- **Repetir la preparación:** si se repite con los mismos originales, `contenido_sha256` tiene que coincidir con el del manifiesto versionado.
- **Recalcular las métricas sin el modelo:** `pytest PoC/paso2_diarizacion -k resultados_publicados` recalcula las métricas desde las hipótesis versionadas y el RTTM local, y las compara con el reporte. Comprobado: coinciden exactamente.
- **Reutilización de la inferencia:** la evaluación de calidad reutiliza una corrida compatible si ya existe en `tests/reportes/calidad/`. `--rehacer` obliga a diarizar otra vez.

## Qué se versiona y qué queda local

| Versionado (en el PR) | Local (excluido de git) |
|---|---|
| Código y pruebas de `PoC/paso2_diarizacion/` | `.venv/`, cachés de Python y de pytest |
| `evaluacion/figshare_test.manifest.json` y `evaluacion/politica_etiquetas.json` | `datos/figshare_test/S26/`: WAV mono y RTTM derivados |
| `evaluacion/resultados/`: `calidad_S26.json`, `calidad_total.json` y `hipotesis_S26/*.json`, sin audio ni rutas locales | `tests/reportes/`: reportes de trabajo y salidas de pyannote con su meta, que incluye rutas absolutas |
| Este documento, los README y `openspec/` del módulo | `hito-2/.cache/`: RAR y extraídos de Figshare |
| `.env.example`, sin valores | `.env`, con el token de Hugging Face; el modelo descargado queda en la caché de Hugging Face del usuario, fuera del repo |

Los resultados en GPU **no están en ninguna de las dos columnas**: quedaron en el equipo de la compañera, y en el repositorio solo figuran los valores que informó (en este documento y en `registro-pruebas.md`). Si los publicara con `publicar_resultados.py`, reemplazaría los JSON de CPU, porque los nombres no incluyen el dispositivo.
