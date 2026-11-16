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
| Selección obtenida (semilla 20261010) | OpenSLR `arf_03398`, `arm_03397`, `arf_01208`; Common Voice `common_voice_es_19635568.mp3` y `common_voice_es_38141239.mp3`; Figshare S22, S23 y S25; AMI IB4005, IS1009c y TS3009a. El clip `common_voice_es_38141239.mp3` es un nombre propio japonés de dos palabras («Keita Kanemoto»); no se reemplazó para no elegir a mano, y Whisper lo transcribió sin errores | 3.1 a 3.3 |
| Dependencias | `transformers` 5.22.1, `sentencepiece` 0.2.2 y `sacremoses` 0.2.0 en `pyproject.toml` y `constraints.txt`, con versiones publicadas antes del 1/11/2026; el encabezado de `constraints.txt` pide acuerdo del equipo | 4.1 |
| Traducción (D6) | `Helsinki-NLP/opus-mt-en-es` en la revisión `5bc4493d` (16/08/2023, Apache 2.0), solo los pesos de PyTorch; búsqueda por haces (`num_beams` del modelo) sin muestreo, en CPU para que cualquiera la repita. Se traduce por oraciones, en fragmentos de hasta 200 palabras (hay turnos de 402 palabras y el modelo corta a 512 tokens), y cada oración distinta una sola vez. Se pierden muletillas como «Um» y «sort of» | 4.1 |
| Roles (D14) | Salen de `corpusResources/meetings.xml` del ZIP original. Traducciones: PM «Gerente de proyecto», ME «Experto en marketing», UI «Diseñador de interfaz», ID «Diseñador industrial». IB4005 no es de escenario y no tiene roles: va con `name: null`, coherente con su referencia, que tampoco nombra responsables | 4.1 |
| Turnos descartados | Los que vienen sin texto en `hito-2/muestra/ami/turnos.parquet` (47 de 580 en IB4005, 42 de 333 en IS1009c, 77 de 579 en TS3009a); ningún turno sin duración ni traducción vacía | 4.1 |
| Manifiesto | `evaluacion/modular/muestra.manifest.json` (versionado): `contenido` determinista con su `contenido_sha256` y `ejecucion` con fecha y versiones. Los datos quedan en `evaluacion/modular/datos/` (ignorado). La muestra se arma en `datos.preparando/` y reemplaza a la anterior solo al terminar | 4.2 |
| Contratos | Validadores públicos de cada etapa: `validar_diarizacion`, `validate_asr_contract`, `validar_transcripcion` más la lectura de la Etapa 5 (`leer_transcripcion`), y para las minutas el modelo de sus secciones más `validar_evidencias`. No se usan los validadores privados del pipeline, que además exigen sus metadatos de corrida. Una salida faltante no cuenta como violación pero impide cumplir el criterio | 5.1 |
| Carpetas | `evaluacion/modular/inferencia/` (ignorada) guarda las salidas, aparte de `datos/`, para que volver a preparar no borre una corrida de GPU. `evaluacion/modular/resultados/` (versionada, con excepción explícita a la regla `resultados/` del `.gitignore`) guarda los reportes, sin rutas de la máquina | 5.1, 5.2 |
| Inferencia (D9, D15) | Un proceso por elemento con el comando de su etapa: `src.stt` (clips), `src.pipeline ejecutar` (Figshare, cadena real 2→3→4→5) y `src.minutas` (AMI); Whisper `medium` y pyannote en CUDA, `qwen2.5-7b` con las 5 secciones. Cada salida lleva `inferencia.json` con el SHA-256 del insumo, la configuración, el comando sin rutas locales y el tiempo; se reutiliza si coinciden y están todos sus archivos | 5.2 |
| Corrida de referencia (16/11/2026) | RTX 3050 Laptop 6 GB, GPU sin otros procesos: 82 elementos en 2 h 4 min (AMI 37,5 min, 3 reuniones de 13 a 16 min; clips 0,9 min; Figshare 86,1 min, mediana 68 s por tarea), sin fallas; pico de VRAM 4870 MiB. `evaluar`: diarización 74/74, STT 79/79, asociación 74/74 y minutas 77/77, 4/4 módulos al 100 %. Una segunda `inferir` reutilizó los 82 sin cargar modelos (0,4 s) | 5.3 |
| Referencia del WER en Figshare (D10) | Frases de los dos canales ordenadas por inicio. Se sacan y se cuentan las etiquetas `<…>`, las palabras cortadas (terminadas en «-») y los tokens sin letras («-?», «?-»); «eh» y «mm-hm» quedan. Normalización: minúsculas y puntuación o símbolos reemplazados por espacios («mm-hm» y «Mm-hm» dan «mm hm»), tildes conservadas. Antes de usarlas se comprueba el SHA-256 de cada archivo de frases contra el manifiesto | 6.1 |
| Agregado del WER | Suma de errores sobre suma de palabras de referencia, por fuente y total; el CER, con Levenshtein por caracteres sobre el texto normalizado. Un elemento sin referencia se informa en `sin_referencia` | 6.1 |
| Resultado del WER (16/11/2026) | OpenSLR 9,1 % (22 palabras), Common Voice 0 % (9), Figshare 27,0 % (13 125; CER 20,1 %), con 2735 borrados de 3540 errores. Excluidos de la referencia de Figshare: 62 etiquetas, 283 fragmentos y 53 tokens sin letras. Sin umbral (§2.3) | 6.1 |
| DER y JER (D10) | Sin copiar código de la Etapa 2: la referencia de cada tarea sale de `leer_anotacion` y `construir` (política de `politica_etiquetas.json`, cuyo SHA-256 queda en el reporte) sobre las frases verificadas contra el manifiesto, y las métricas de `der.Evaluador`, con su misma configuración (estricto, NIST ±0,25 s, JER; con superposición; región evaluada [0, duración]). Agregado por sesión y total, ponderado por el tiempo como en S26 | 6.2 |
| Resultado del DER (16/11/2026) | Total: DER estricto 21,3 %, DER NIST 10,7 %, JER 41,0 % (S22 18,9 %, S23 28,4 %, S25 20,2 % de DER estricto). La confusión es el 53 % del error (436 de 820 s). Cantidad de hablantes correcta en 65 de 74 tareas (en 9 detectó uno solo). Valores cercanos a los de S26 en la evaluación de la Etapa 2 (23,1 %, 12,3 % y 40,0 %). Sin umbral | 6.2 |
| Atribución de palabras (D10) | El hablante de cada palabra se reconstruye con el mismo recorrido de `armar_intervenciones` (`Turnos` y el `asr.json` normalizado que devuelve `asociar()`), sin tocar `src/asociacion`; si los conteos (palabras, D2, D3, sin hablante) no coinciden con los de `asociar()`, la evaluación falla. Se compara el punto medio de cada palabra con los canales de referencia activos, usando la correspondencia de etiquetas del DER estricto (`optimal_mapping`) | 6.3 |
| Limitación de la atribución | Con dos o más canales activos se acepta cualquiera de ellos: la referencia no dice de quién es cada palabra dentro de una superposición. En Figshare, con dos personas, ese grupo da casi siempre 100 % y no es informativo; el valor que mide la asociación es el de las palabras sin superposición | 6.3 |
| Resultado de la atribución (16/11/2026) | 87,3 % de 9492 palabras (S22 91,5 %, S23 82,7 %, S25 86,9 %); sin superposición 86,1 % (8720 palabras). 801 palabras caen fuera del habla de referencia y 1 quedó sin hablante. Marcas: las 318 intervenciones con `overlap` caen sobre superposición real (cubren 318 de las 615 que la tocan); 184 de 262 `ambiguous` también. Sin umbral | 6.3 |
| Planilla de minutas (D10, D17) | `resultados/planillas/` (versionada): por reunión, `<reunión>.csv` con un ítem de referencia por fila (tipo, texto traducido, original en inglés) y las columnas `recuperado` (sí o no) y `observaciones`, más `<reunión>.minuta.md` con la minuta producida y un `LEEME.md` con el criterio de §2.3 (una acción cuenta solo con su responsable). Una planilla existente nunca se reescribe; un valor que no es sí o no hace fallar `evaluar` nombrando el ítem; si la minuta cambia después de generar la planilla, se avisa y se conserva la copia. 56 ítems en las 3 reuniones (IB4005 25, IS1009c 19, TS3009a 12) | 6.4 |
| Evaluación sin GPU | `evaluar` no importa modelos (ni torch, ni Whisper, ni pyannote.audio, ni transformers, ni Ollama). Se comprueba en un proceso aparte con `CUDA_VISIBLE_DEVICES` vacío; con las salidas de la corrida de referencia reproduce byte a byte los reportes versionados. Estos tests pasaron desde el primer intento: el requisito ya lo cumplía el diseño de las tareas 5.1 a 6.4 | 6.5 |
| Exposición previa | Declaración versionada en `evaluacion/modular/exposicion.toml`, con evidencia por fuente y por modelo de los módulos que alimenta; `evaluar` la combina con las exclusiones del manifiesto en `resultados/exposicion.json` y falla si falta una fuente o un modelo. Lo que no se puede verificar se declara como «no se puede descartar». Pendiente: S22 y S23 fueron el alcance inicial de la evaluación de la Etapa 2 (hasta el 08/11/2026); en el repositorio no hay resultados con ellas, pero falta que lo confirme la responsable de la Etapa 2 | 7.1 |
| Adaptación al PR #19 (16/11/2026) | El #19 cambió la asociación (alineación literal palabra-texto y respaldo por segmento, `transcription.json` con `timing`, `speakers_detected` y `source`) y las minutas. La reconstrucción por palabra copiada de `armar_intervenciones` dejó de coincidir (la protección la detectó: 108 contra 91 palabras en S22-01). Ahora el hablante de cada palabra sale de las intervenciones de `asociar()`: `source` da el segmento y el tramo de texto, y `alinear()` el tramo de cada palabra; las intervenciones por segmento (`timing` «segment» o «unknown») se cuentan aparte en `respaldo`, fuera del porcentaje | 6.3 |
| Huella de código | La reutilización de `inferir` incluye un SHA-256 del código y los prompts de las etapas de cada tipo (`src/stt` para clips; `src/minutas` para AMI; ingesta, diarización, STT, asociación, minutas y pipeline para Figshare). Al cambiar ese código, el elemento se vuelve a correr; en Figshare el pipeline reutiliza por su cuenta las etapas vigentes (comprobado: tras el #19 rehízo solo la asociación y la minuta) | 5.2 |
| Salidas versionadas | `evaluar` publica en `resultados/salidas/` (versionado, unos 2 MB, sin audio ni rutas locales) los JSON de cada módulo, la minuta en Markdown y el `inferencia.json` de cada elemento. Sin `inferencia/` local, `evaluar` lee de ahí: en otra máquina alcanza con `preparar` (CPU) y `evaluar`, sin GPU | 6.5 |
| Muestra congelada (revisión del #20) | `preparar` arma la muestra aparte y solo la publica si no hay una congelada o si tiene el mismo `contenido_sha256`; en ese caso renueva los datos y no reescribe el manifiesto. Con otro hash falla sin tocar nada, salvo `--reemplazar` | 4.2 |
| Secciones de las minutas (revisión del #20) | El contrato de minutas exige las secciones de `[modelos].secciones` de la configuración: una minuta que declara otras (por ejemplo, solo el resumen) queda fuera de contrato | 5.1 |
| Asociación contra el ASR (revisión del #20) | El contrato de asociación se valida con `validar_transcripcion(..., asr=...)` sobre el ASR normalizado por `validar_asr`, como lo recibe la Etapa 4: comprueba la cobertura literal del texto de cada segmento (contrato de preservación textual del #19) | 5.1 |
| Integridad de lo reutilizado (revisión del #20) | `inferencia.json` guarda el SHA-256 de cada salida esperada; `inferir` reutiliza solo si coinciden y, en Figshare, si `workflow.json` del pipeline está «completado». Las 82 salidas de la corrida con el #19 se sellaron después de la corrida, solo tras comprobar que eran idénticas byte a byte a `resultados/salidas` versionado en `4fd427e` | 5.2 |
