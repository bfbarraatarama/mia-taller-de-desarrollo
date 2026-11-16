# Design

## Contexto

La muestra de §2.3 tiene tres fuentes con usos distintos:

| Fuente | En el repo | Referencia | Módulos que evalúa |
|---|---|---|---|
| OpenSLR 61 (habla leída, rioplatense) | 44 clips FLAC de 48 kHz en `hito-2/muestra/slr61/clips` (locales); transcripciones versionadas | Texto por clip | STT |
| Common Voice 26 rioplatense | No; se baja con `descargar_fuentes.py common_voice` y `MDC_API_KEY` | Texto por clip | STT |
| UBA Games, Figshare v2 | No; `descargar_fuentes.py uba_games_figshare` baja `phrases.rar` y `wavs.rar` (722 MB, MD5 en `fuentes.toml`) | Frases con inicio, fin y texto por canal (un participante por canal) | STT, diarización, asociación y la cadena 2→3→4→5 |
| AMI | Turnos, minutas y reuniones en `hito-2/muestra/ami` (versionados) | Ítems de resumen, decisión, problema y acción | Minutas |

Figshare v2 tiene 9 sesiones de dos participantes y 219 tareas. Según el README de origen, S26 a S30 vienen de `annotations_incompleto`. S26 se usó para desarrollar: la evaluación de diarización (`evaluacion/diarizacion/EVALUACION_S26.md`) y las mediciones que fijaron D6 de la asociación (`evaluacion/asociacion/stats_s26.py`).

AMI con minuta: 142 reuniones de 37 series, de 11 a 56 minutos (mediana 34 min, unas 5000 palabras); 306 ítems de acción en total. No hay ninguna traducción al castellano en el repo.

Semilla de toda selección: `20261010`, la del Hito 2.

## Decisiones

### D1. Clips de transcripción

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **3 de OpenSLR 61 y 2 de Common Voice** | **Elegida** |
| B | 5 de OpenSLR 61, sin descargar nada | Descartada: se aparta de §2.3 y deja un solo tipo de grabación (de estudio) |
| C | 5 de OpenSLR ahora y Common Voice después | Descartada: la muestra se congelaría dos veces y el manifiesto cambiaría después de evaluar |

Motivo: cumple §2.3 tal como está escrita; Common Voice suma voces y condiciones de grabación distintas.

### D2. Selección de los clips

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **5 personas distintas, ambos géneros; Common Voice del split `test` oficial; semilla** | **Elegida** |
| B | Los clips más largos | Descartada: criterio propio que sesga hacia oraciones largas |
| C | Al azar sin restricciones | Descartada: con 5 clips puede repetir persona o género |

Motivo: el Hito 2 separa por hablante; `test` evita los clips más expuestos a entrenamiento.

### D3. Sesiones de Figshare

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **3 sesiones nuevas, sin S26** | **Elegida** |
| B | 3 grabaciones de S26 | Descartada: es material de desarrollo y una sola sesión |
| C | S26 y 2 sesiones nuevas | Descartada: mezcla datos expuestos con limpios |

Motivo: sin exposición previa y con otras voces.

### D4. Unidad de Figshare

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **Sesiones completas (todas sus tareas)** | **Elegida** |
| B | Una tarea por sesión | Descartada: 3 audios cortos dan métricas anecdóticas |
| C | Tareas de una sesión unidas en un audio | Descartada: cortes artificiales y referencias desplazadas |

Motivo: es lo que dice §2.3 («3 sesiones») y da unas 75 grabaciones con referencia.

### D5. Elección de las 3 sesiones

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **Solo sesiones con anotación completa (fuera S26 a S30); 3 con la semilla** | **Elegida** |
| B | Por diversidad de hablantes (`subjects-info`) | Descartada: criterio propio; puede elegir anotaciones incompletas |
| C | Al azar entre las 8 restantes | Descartada: puede caer en S27 a S30 |

Motivo: una referencia incompleta infla los errores sin que el sistema falle; la semilla evita elegir las sesiones «que andan».

### D6. Traducción de AMI

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **MarianMT local (`Helsinki-NLP/opus-mt-en-es`)** | **Elegida** |
| B | LLM remoto (Claude por Bedrock) | Descartada: no determinista, con credenciales y costo |
| C | Qwen 2.5 7B local | Descartada: es el modelo evaluado; traduce y resume él mismo |

Motivo: local, determinista y sin credenciales, así que cualquiera la repite; distinto del modelo que se evalúa.

### D7. Qué se traduce de AMI

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **Turnos e ítems de la minuta de referencia** | **Elegida** |
| B | Solo los turnos | Descartada: la comparación se haría entre idiomas |
| C | Turnos, y la minuta solo por contrato | Descartada: no deja medida de contenido |

Motivo: la minuta de la PoC se compara con una referencia en el mismo idioma y con la misma terminología. Ambas traducciones quedan marcadas como sintéticas.

### D8. Reuniones de AMI

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **3 series distintas, cada una con al menos un ítem de acción y duración cerca de la mediana; semilla** | **Elegida** |
| B | Una serie completa | Descartada: mismas personas y mismo tema |
| C | Las 3 más cortas | Descartada: atípicas; no ejercitan la fragmentación de minutas largas (#17) |

Motivo: el Hito 2 separa por serie; §2.3 mide acciones.

### D9. Recorrido de la evaluación

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **Cada módulo con su referencia y, además, la cadena real 2→3→4→5 en Figshare** | **Elegida** |
| B | Solo por módulo, con entradas de referencia | Descartada: no prueba que la salida real entre en el módulo siguiente |
| C | Solo la cadena real | Descartada: no separa qué módulo falló |

Motivo: separa errores por módulo y cubre lo que mide §2.3, el contrato entre módulos.

### D10. Métricas sin umbral

| Módulo | Métrica | Elegida entre |
|---|---|---|
| STT | WER y CER con minúsculas y sin puntuación, conservando tildes | Normalizador de Whisper (caja negra pensada para inglés) · WER crudo (cuenta mayúsculas y comas) |
| Diarización | DER estricto y con tolerancia NIST (±0,25 s) y JER, con `evaluacion/diarizacion/der.py` | Precisión de la Etapa 2: misma configuración que S26 para poder comparar |
| Asociación | % de palabras atribuidas al hablante correcto, con y sin superposición, e intervenciones `ambiguous` sobre superposición real | WDER (junta errores de los tres módulos) · solo contrato y conteos (sin referencia) |
| Minutas | Planilla sí/no por ítem de referencia, marcada por una persona | LLM como juez (sesgo, costo, no determinista) · embeddings (umbral arbitrario) |

Motivo: cada métrica mide la decisión propia del módulo; la planilla de minutas usa el mismo método que el criterio de calidad de §2.3.

### D11. Ejecutor

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **Tres comandos: `preparar`, `inferir` y `evaluar`, con configuración TOML versionada** | **Elegida** |
| B | Un solo comando | Descartada: recalcular una métrica obliga a inferir otra vez |
| C | Notebook | Descartada: el issue pide línea de comandos; difícil de revisar en un PR |

Motivo: cumple «recalcular sin inferir» y sigue el patrón de `preparar_figshare.py`.

### D12. Ubicación

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **SDD en `docs/evaluacion/openspec/`; código en `evaluacion/modular/`** | **Elegida** |
| B | Todo dentro de `evaluacion/modular/` | Descartada: rompe la convención de `docs/` que dejó la integración |
| C | Sin OpenSpec, solo un README | Descartada: pierde el registro de decisiones |

### D13. Obtención de los originales

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **Common Voice lo baja Matías con su cuenta; `wavs.rar`, el asistente con su ok, verificando el MD5** | **Elegida** |
| B | Matías baja todo | Descartada por comodidad, no por riesgo |
| C | Copiar los RAR de Bruno | Descartada: hay que coordinar la transferencia y verificar igual |

### D14. Entrada de la Etapa 5 en AMI

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **`speaker` = letra del participante; `name` = su rol de AMI traducido; `overlap` con la regla D5 de la asociación sobre los tiempos de referencia; `ambiguous: false`** | **Elegida** |
| B | Etiqueta sin nombre (`name: null`) | Descartada: las acciones salen con la etiqueta y la referencia nombra el rol |
| C | Pasar por la Etapa 4 con `asr.json` y diarización de referencia | Descartada: mezcla la evaluación de minutas con la de asociación (D9) |

Motivo: las acciones de referencia nombran a los responsables por su rol («The industrial designer will…»); así la minuta puede asignarlos igual. Los roles salen del ZIP original de AMI (`hito-2/.cache/ami/ami_public_manual_1.6.2.zip`).

### D15. Modelo de la Etapa 5

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **`qwen2.5:7b` local, todas las secciones, con la configuración del pipeline registrada** | **Elegida** |
| B | `qwen2.5:7b` y Claude remoto | Descartada: §1.3 deja fuera la comparación de modelos; duplica el marcado |
| C | Solo Claude remoto | Descartada: no es el *baseline* de §3.1.1 |

Motivo: evalúa el sistema que define la PoC, en la máquina de referencia y sin credenciales.

### D16. Audio de Figshare para la cadena

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **Mezcla mono `(L + R) // 2`, como la evaluación de la Etapa 2** | **Elegida** |
| B | Un archivo por canal | Descartada: diarización y asociación triviales, sin superposición |
| C | Mezcla para la cadena y canales para el WER por hablante | Descartada: duplica el STT sin cambiar el criterio |

Motivo: equivale a una reunión grabada con un micrófono y deja los DER comparables con S26.

### D17. Marcado de la planilla de minutas

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **Un integrante que no ejecutó la inferencia (Felipe o Luisa), sobre un CSV que genera `evaluar`** | **Elegida** |
| B | Matías, que ejecutó la inferencia | Descartada: sesgo de quien conoce la salida |
| C | Dos personas y su acuerdo | Descartada: duplica el trabajo; con unos 80 ítems el acuerdo es poco estable |

Motivo: es el mismo resguardo que §2.3 pide para las notas de la reunión de prueba.

## Precisiones de la implementación

| Tema | Precisión | Tarea |
|---|---|---|
| Hashes de los originales | No se repiten en `config.toml`: salen de `hito-2/fuentes.lock.json`; si un archivo no está fijado, del MD5 publicado en `hito-2/fuentes.toml` | 2.1 |
| Common Voice | El `.tar.gz` bajado desde la web de Mozilla Data Collective tiene otro nombre pero el mismo SHA-256 y tamaño que el fijado; se guarda en la caché con el nombre del lock | 2.2 |
| Clips (D2) | OpenSLR 61 (31 mujeres y 13 hombres): una mujer, un hombre y un tercer hablante al azar entre los restantes. Common Voice: un clip `female_feminine` y uno `male_masculine` del split `test` (224 clips, 110 personas); quedan fuera los 63 sin género declarado. Un clip al azar por hablante | 3.1 |
| Sesiones (D5) | Candidatas S21 a S25: el README de `wavs.rar` indica que S26 a S30 vienen de «annotations_incompleto» y que la S28 no está. Cada exclusión queda con su motivo | 3.2 |
| Reuniones (D8) | «Cerca de la mediana»: duración entre los percentiles 25 y 75 (cuartiles inclusivos) de las reuniones con minuta y al menos una acción; se sortean y se toma la primera de cada serie hasta tener 3 | 3.3 |
| Determinismo | Cada inventario se ordena antes de sortear con `random.Random(semilla)`, así el orden de lectura no cambia la selección | 3.1 a 3.3 |
| Normalización | Cada elemento es una carpeta de reunión hecha con `ingestar` de `src/ingesta` (FFmpeg a 16 kHz, mono, PCM16), la misma de la aplicación. Los miembros se leen de los originales sin extraerlos | 3.4 |
| Canales de Figshare | S21 a S25 vienen en dos WAV mono por tarea (`channel1` y `channel2`); la mezcla es `(L + R) // 2` en enteros, con hasta 1 cuadro de diferencia entre canales (criterio de la Etapa 2) | 3.4 |
| 7-Zip | Los RAR se leen con `src/rar7z`; en Fedora hace falta `SIETE_ZIP` apuntando a un 7-Zip con RAR (hallazgo del #18) | 3.2, 3.4 |
| Selección obtenida (semilla 20261010) | OpenSLR `arf_03398`, `arm_03397`, `arf_01208`; Common Voice `common_voice_es_19635568.mp3` y `common_voice_es_38141239.mp3`; Figshare S22, S23 y S25; AMI IB4005, IS1009c y TS3009a. Limitación: el clip `common_voice_es_38141239.mp3` es un nombre propio japonés de dos palabras; no se reemplaza para no elegir a mano | 3.1 a 3.3 |
| Dependencias | `transformers` 5.22.1, `sentencepiece` 0.2.2 y `sacremoses` 0.2.0 en `pyproject.toml` y `constraints.txt`, con versiones publicadas antes del 1/11/2026; el encabezado de `constraints.txt` pide acuerdo del equipo | 4.1 |
| Traducción (D6) | `Helsinki-NLP/opus-mt-en-es` en la revisión `5bc4493d` (16/08/2023, Apache 2.0), solo los pesos de PyTorch; búsqueda por haces (`num_beams` del modelo) sin muestreo, en CPU para que cualquiera la repita. Se traduce por oraciones, en fragmentos de hasta 200 palabras (hay turnos de 402 palabras y el modelo corta a 512 tokens), y cada oración distinta una sola vez. Se pierden muletillas como «Um» y «sort of» | 4.1 |
| Roles (D14) | Salen de `corpusResources/meetings.xml` del ZIP original. Traducciones: PM «Gerente de proyecto», ME «Experto en marketing», UI «Diseñador de interfaz», ID «Diseñador industrial». IB4005 no es de escenario y no tiene roles: va con `name: null`, coherente con su referencia, que tampoco nombra responsables | 4.1 |
| Turnos descartados | Los que vienen sin texto en `hito-2/muestra/ami/turnos.parquet` (47 de 580 en IB4005, 42 de 333 en IS1009c, 77 de 579 en TS3009a); ningún turno sin duración ni traducción vacía | 4.1 |
| Manifiesto | `evaluacion/modular/muestra.manifest.json` (versionado): `contenido` determinista con su `contenido_sha256` y `ejecucion` con fecha y versiones. Los datos quedan en `evaluacion/modular/datos/` (ignorado). La muestra se arma en `datos.preparando/` y reemplaza a la anterior solo al terminar | 4.2 |
| Contratos | Validadores públicos de cada etapa: `validar_diarizacion`, `validate_asr_contract`, `validar_transcripcion` más la lectura de la Etapa 5 (`leer_transcripcion`), y para las minutas el modelo de sus secciones más `validar_evidencias`. No se usan los validadores privados del pipeline, que además exigen sus metadatos de corrida. Una salida faltante no cuenta como violación pero impide cumplir el criterio | 5.1 |
| Carpetas | `evaluacion/modular/inferencia/` (ignorada) guarda las salidas, aparte de `datos/`, para que volver a preparar no borre una corrida de GPU. `evaluacion/modular/resultados/` (versionada, con excepción explícita a la regla `resultados/` del `.gitignore`) guarda los reportes, sin rutas de la máquina | 5.1, 5.2 |
| Inferencia (D9, D15) | Un proceso por elemento con el comando de su etapa: `src.stt` (clips), `src.pipeline ejecutar` (Figshare, cadena real 2→3→4→5) y `src.minutas` (AMI); Whisper `medium` y pyannote en CUDA, `qwen2.5-7b` con las 5 secciones. Cada salida lleva `inferencia.json` con el SHA-256 del insumo, la configuración, el comando sin rutas locales y el tiempo; se reutiliza si coinciden y están todos sus archivos | 5.2 |
