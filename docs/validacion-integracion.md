# Validación de la integración

La validación técnica comprueba que la PoC integra los componentes a través de la API, la terminal y la interfaz. No determina el veredicto académico: los criterios y umbrales de aceptación siguen siendo los de [la definición de la PoC, §2.3](../hito-3/definicion-de-la-poc.md#23-criterios-de-aceptación). Se separan las pruebas con sustitutos de modelos, las ejecuciones con inferencia real y la evaluación de calidad. Un resultado estructuralmente conforme no demuestra que el contenido de una minuta sea fiel al audio ni que el sistema detecte correctamente a todos los hablantes.

## Comprobaciones reproducibles

Usar el [entorno único del repositorio](../README.md#entorno-único-para-todo-el-repositorio). Desde la raíz, en Linux con CUDA y PipeWire:

```bash
.venv/bin/python -m compileall -q src tests evaluacion hito-2/scripts
.venv/bin/python -m pytest -q -rs
pw-jack .venv/bin/python -m src.verificar_entorno --gpu
.venv/bin/python -m evaluacion.diarizacion.preparar_figshare --verificar
```

La última comprobación exige datos preparados localmente; véanse los [procedimientos de evaluación de diarización](../evaluacion/diarizacion/README.md). El verificador no ejecuta inferencias. La suite ordinaria excluye las pruebas de diarización `slow`, `calidad` y `gpu`; no se contabilizan como aprobadas. Los niveles de prueba se describen en la [guía de diarización](diarizacion/README.md). En particular, el nivel `slow` utiliza `DIARIZACION_AUDIOS_CPU` con grabaciones y reportes de captura, no una carpeta con WAV cualesquiera. El nivel de calidad puede reutilizar resultados compatibles: usar `--rehacer` si se busca una nueva inferencia. Registrar omisiones, modalidad y motivo, sin modificar la configuración para forzar un resultado positivo.

## Evidencia de integración

### Integración inicial, entorno y organización (14/11/2026)

La integración inicial (`e357b3b`) verificó el recorrido con un WAV público de Figshare mediante API y Qwen local, la interfaz con identificación, varios cortes concatenados con identidad PCM, una generación remota autorizada y cancelación con conservación de etapas anteriores. También se procesó el audio recuperado de una captura interrumpida. Estas comprobaciones identificaron cuestiones de vigencia, restauración y presentación que motivaron las correcciones posteriores; no se consideran pruebas de calidad formal.

Con la consolidación de dependencias (`b3711e6`) en Ubuntu 24.04, Python 3.12.3 y RTX 4060 Ti, el verificador informó 29 dependencias directas, 198 restricciones compatibles, CUDA disponible, cero fallas y cero avisos. La instalación editable conservó las versiones ya instaladas; no fue una instalación desde cero. Las suites ejecutadas por separado registraron 547 pruebas y 52 subtests aprobados, cinco omisiones y seis deselecciones.

La reorganización de paquetes, pruebas y evaluación (`47f613d`) permitió ejecutar las suites en conjunto y restableció cuatro comprobaciones de resultados publicados que antes quedaban omitidas por rutas incorrectas. Se registraron 554 pruebas y 52 subtests aprobados, una omisión por presencia de CUDA y seis deselecciones. Se verificaron los 25 pares WAV mono y RTTM de S26 y su `contenido_sha256` sin modificar el manifiesto. Tras retirar la antigua carpeta local de trabajo se repitieron el verificador, el control de S26 y la suite con los mismos resultados. Una nueva ejecución desde la interfaz con el WAV público S26 04, Whisper `medium`, dispositivo automático y Qwen local produjo los cinco grupos de artefactos completos, incluida la identificación. Estos resultados sustentan el cierre de la integración estructural, no el cumplimiento de los criterios de aceptación del Hito 3.

### Mejoras posteriores de integración

La referencia de desarrollo `5157e71` (árbol `8ef1e9b29d614f5d4e1d1cf97a10ef944546e97c`) pasó 730 pruebas ordinarias, 52 subtests, una omisión por presencia de CUDA y seis deselecciones. Las siguientes comprobaciones se apoyan también en ejecuciones anteriores de la integración de noviembre de 2026. Las rutas mencionadas son directorios locales de evidencia, no datos incluidos en Git ni requisitos de instalación. No deben compartirse originales privados, credenciales o transcripciones no autorizadas. Los contadores y tiempos de esas ejecuciones corresponden a sus propias versiones, no a nuevas mediciones del árbol actual.

| Aspecto | Evidencia de integración | Alcance o limitación |
|---|---|---|
| API y audio único | ejecución real con Qwen local, Whisper medium y pyannote; `resultados/verificacion-api`; notebook ejecutado con Nova Lite | lectura de resultados vigentes; no mide calidad semántica |
| Varios WAV, orden y offsets | pruebas de ingesta y recorrido CLI real con dos cortes de Figshare | identidad del PCM concatenado comprobada |
| GUI e identificación | reapertura, nombres, cancelación de identificación, resultados y temas; `resultados/verificacion-unidad-c-gui`; regresión exploratoria extensa | se conserva la evidencia anterior; persistencia del tema cubierta por pruebas automatizadas |
| Secciones y proveedores | esquemas, referencias, fragmentación y adaptadores simulados; inferencias reales con Qwen, Nova Lite y Claude Opus 4.5 | disponibilidad observada en las ejecuciones descritas, no certificación permanente |
| Reutilización e invalidación | pruebas de dependencia, corrupción, medición y bloqueo; `resultados/verificacion-unidad-b` y `resultados/verificacion-unidad-c-gui`; regresiones de versiones de consolidación y asociación | las nuevas claves se verificaron con sustitutos de modelos |
| Errores y transferencias | fallos inyectados y denegación; rechazo de autorización en la GUI; ejecución remota autorizada del notebook | no se prueba exhaustivamente toda falla posible de un proveedor |
| Cancelación y recuperación | cancelación real; grabación recuperada y procesada después de un cierre forzado; recuperación persistente, posposición y omisión comprobadas en la GUI | evidencia previa, no repetición del protocolo académico |
| Presentación | visores en ambos temas, agrupación y originales; pruebas de Qt y de lógica de presentación | la agrupación visual no cambia el JSON canónico |

La prueba previa de grabación interrumpida registró un corte a 131,118 s y un archivo de 130,250 s (pérdida estimada de 0,868 s, con incertidumbre aproximada de un segundo); se procesó el WAV recuperado. Es evidencia técnica útil, no sustituye el protocolo académico y su registro independiente. Ante la atribución observada de toda una transcripción a una misma etiqueta no se ha demostrado si el origen es diarización, ASR o asociación; no corresponde cambiar el algoritmo basándose solo en esa observación.

La primera revisión de integración sobre `5157e71` con ajustes documentales y de clientes (árbol `a2da854b0b8460d4bcc3fc87bb14669f1d2278cd`) registró 732 pruebas ordinarias y 52 subtests aprobados, una omisión y seis deselecciones, código de salida 0. En Linux con Python 3.12.3, RTX 4060 Ti y CUDA, el verificador del entorno informó cero fallas y avisos; los 25 pares WAV/RTTM preparados de Figshare y su `contenido_sha256` coincidieron. Esta evidencia precede al ajuste de consolidación y no constituye una inferencia de ese ajuste.

La regresión de [consolidación](minutas/consolidacion-de-minutas.md) reproduce con datos sintéticos el bloqueo que se producía si ningún grupo de dos parciales cabía en el presupuesto. Incluye límites del modelo, las combinaciones de secciones, conservación de referencias, fallos de formato, límites de subdivisión y reutilización de checkpoints. La cobertura técnica no garantiza síntesis semántica ni calidad; corresponde verificar el funcionamiento con cada proveedor real usando solo datos autorizados.

El árbol `25d978d1769a477d5b5c62fc6969c895d163d184`, que incorpora las correcciones de consolidación, pasó en el entorno Linux con CUDA 801 pruebas ordinarias y 52 subtests, una omisión y seis deselecciones; código de salida 0. La regresión focalizada de minutas e integración pasó 300 pruebas y 52 subtests. Estas ejecuciones preceden al ajuste temporal posterior.

La corrección de [temporalidad de la transcripción](temporalidad-transcripcion.md) cubre con datos sintéticos el colapso de intervalos por redondeo, los límites de intervención ante marcas fuera de orden y la pérdida de un milisegundo en duraciones exactamente representables. Incluye una regresión de compatibilidad y regeneración selectiva. No demuestra la frecuencia de estos casos en resultados reales ni introduce umbrales de evaluación de calidad.

El árbol `0621e03626175a453299631946707b557b86d0e9`, que incorpora también las correcciones temporales, pasó 820 pruebas ordinarias y 52 subtests en Linux con CUDA, con una omisión, seis deselecciones y código de salida 0.

### Regresión exploratoria con una reunión extensa

Se realizó una ejecución integral mediante la interfaz gráfica con una grabación privada de 3123,561 s (52 min 3,6 s), ajena a la muestra de evaluación. La solicitud terminó en estado `completado`, sin ejecución activa y con las cinco etapas vigentes.

La configuración efectiva fue pyannote `speaker-diarization-community-1` (CUDA, cantidad de hablantes no prefijada), Whisper `medium` (CUDA) y Claude Opus 4.5 mediante AWS Bedrock (`us.anthropic.claude-opus-4-5-20251101-v1:0`), con las cinco secciones habilitadas. Se configuraron temperatura 0,0, máximo de salida de 4096 tokens, presupuesto de 12000 caracteres y dos reintentos de formato. El parámetro `num_ctx=16384` quedó registrado, pero solo condiciona el contexto de Ollama. El manifiesto registró 20 llamadas al modelo y contadores acumulados de 117429 tokens de entrada y 20233 de salida.

Se registraron los siguientes tiempos:

| Etapa | Tiempo (s) |
|---|---:|
| Preparación | 2,719 |
| Diarización | 132,759 |
| Transcripción | 193,083 |
| Asociación | 0,159 |
| Generación de minutas | 262,478 |
| Latencia activa total | 591,993 |
| Espera de identificación (excluida de la latencia activa) | 53,873 |

El manifiesto de consolidación (versión 2) registró 15 bloques iniciales, ninguna subdivisión de extracción y dos niveles de consolidación. Se realizaron dos uniones locales: una por presupuesto y otra por pérdida de cobertura de evidencias. Se sintetizaron dos resúmenes sin recurrir a la concatenación. El máximo observado de datos enviados fue de 11973 caracteres (12053 bytes), según los contadores del manifiesto; estos no representan el tamaño completo de la solicitud al proveedor.

La ejecución comprueba que la recuperación por presupuesto se activó y que el flujo pudo finalizar sin el bloqueo de consolidación observado anteriormente. Se registran únicamente indicadores técnicos agregados; el audio, las transcripciones, las minutas y el resto de los artefactos permanecen privados. Esta es evidencia preliminar de funcionamiento, no reproducible por terceros a partir del repositorio. No se evaluó la calidad semántica de la minuta ni se verifican con ella los criterios de aceptación del Hito 3.

## Ejecuciones reales de cierre

Utilizar material permitido, separado de las reuniones de uso personal. Mantener directorios de salida nuevos para no sobrescribir evidencias anteriores. La API pública y sus opciones están en el [README raíz](../README.md#ejecución-programática); el [notebook integral](../notebooks/workflow_poc.ipynb) es un cliente de esa API. Editar rutas en una copia local del notebook, seleccionar el kernel del entorno raíz y ejecutar las celdas en orden. La prueba automatizada correspondiente ejecuta sus celdas con inferencias sustituidas; no equivale a la ejecución de un kernel con modelos reales.

Para comprobar una reunión, consultar `python -m src.pipeline estado --reunion DIRECTORIO`: se espera `completado`, `activa=false`, cinco etapas vigentes y los artefactos contractuales. Registrar versiones, configuración, orden y huellas de fuentes, duración y medición de la solicitud. Comparar los límites de muestras de `ingesta.json` con la longitud de los archivos normalizados; si los cortes proceden del mismo PCM, contrastar el audio concatenado con ese PCM. La comprobación de vigencia valida hashes y contratos, no contenido semántico. Conservar los resultados de cada generación antes de cambiar de modelo, dado que `workflow.json` representa la solicitud vigente y no es un historial de ejecuciones.

Para Bedrock u otro destino externo, consultar [Reanudación y confidencialidad](continuidad-y-confidencialidad.md#confidencialidad-y-consentimiento). No enviar datos a un proveedor para verificar la disponibilidad sin autorización. La opción `--permitir-remoto` solo se añade a una solicitud cuando existe consentimiento para su destino concreto. Registrar éxito o error real del proveedor, modelo y número de llamadas a partir de `ejecucion_minutas.json`; la presencia del modelo en el catálogo no certifica disponibilidad. No comparar latencias remotas con las locales como si se hubieran ejecutado en el mismo hardware.

### Resultados de cierre (15/11/2026)

Se completaron dos recorridos con inferencia real, ambos con pyannote `speaker-diarization-community-1` y Whisper `medium`, solicitados en CUDA, sin pausa de identificación. Las cinco etapas quedaron vigentes y el estado final fue `completado` en ambos casos.

- CLI: se dividió `evaluacion/diarizacion/datos/figshare_test/S26/figshare_v2_S26_objects_04.wav` (SHA-256 `ead1afa6229bc4a53ca7d926d9f4edf85d3f75af8edfc7fc9e92f92bde1c8638`, PCM mono de 16 bits a 16000 Hz) en dos WAV de 418166 y 418167 muestras, sin recodificación. Se pasaron en ese orden a `src.pipeline ejecutar`, con `--modelo-stt medium --dispositivo-stt cuda --dispositivo-diarizacion cuda --modelo qwen2.5-7b --secciones resumen,temas,acciones` y un directorio de salida nuevo. Los offsets fueron [0, 418166) y [418166, 836333); el PCM concatenado coincidió muestra por muestra con el original. Se verificaron el destino `ollama_local` y las secciones seleccionadas.
- Notebook: se generó el audio de prueba mediante `python -m evaluacion.asociacion.ejemplo_ideal.generar --salida resultados/verificacion-unidad-e-sintetica`. Se ejecutó una copia del notebook con ese `audio.wav`, un directorio de salida nuevo, Whisper medium, ambos dispositivos en CUDA, identificación omitida y `nova-lite` con las cinco secciones; se autorizó expresamente el destino AWS Bedrock (us-west-1). Se empleó un kernel temporal del entorno virtual con comunicación IPC. No se usaron las referencias ideales de ASR o diarización como sustitutos de inferencia. Se corrigió la comprobación de rutas del notebook para admitir `str` y `Path`, con una regresión parametrizada.

| Indicador | CLI / Qwen 2.5 7B | Notebook / Amazon Nova Lite |
|---|---:|---:|
| Duración del audio (s) | 52,2708125 | 60,764 |
| Preparación (s) | 0,095 | 0,057 |
| Diarización (s) | 6,614 | 6,536 |
| Transcripción (s) | 10,179 | 10,454 |
| Asociación (s) | 0,006 | 0,006 |
| Minutas (s) | 11,672 | 4,128 |
| Latencia activa total (s) | 28,608 | 21,225 |
| Llamadas al modelo de minutas | 1 | 1 |
| Bloques iniciales | 1 | 1 |
| Niveles de consolidación | 0 | 0 |
| Uniones locales | 0 | 0 |

Nova Lite (`us.amazon.nova-lite-v1:0`) registró 2447 tokens de entrada y 449 de salida. La lectura del manifiesto confirmó el destino `bedrock` y las cinco secciones. Los registros locales están en `resultados/verificacion-unidad-e-cli`, `resultados/verificacion-unidad-e-notebook` y `resultados/verificacion-unidad-e-notebook-ejecutado.ipynb`. Son evidencia funcional, no una comparación controlada de rendimiento o calidad entre modelos.

La regresión final del código (árbol `819b4c2fbcec8811c6dbd2b9e9f94555168a8513`, anterior a esta actualización exclusivamente documental) pasó 821 pruebas ordinarias y 52 subtests, con una omisión por presencia de CUDA, seis deselecciones, compilación sin errores y código de salida 0. No se ejecutaron los seis casos deseleccionados como parte de esa suite.

## Preservación textual y tratamiento de incertidumbres

La versión 0.4.0 de asociación incorpora la regresión de una negación sin intervalo de palabra válido. En el caso sintético, el segmento «No aprobar el cambio» tiene intervalo [0; 2] s y la palabra «No» tiene duración nula. Se reproduce el mecanismo de pérdida sin depender de los tiempos exactos de la grabación que motivó la revisión ni de una inferencia. La salida conserva el texto completo con resolución por segmento. Las pruebas incluyen discordancias entre texto y palabras, signos de puntuación, repeticiones, recortes, intervalos desconocidos, órdenes incompatibles, empates, huecos y actividad simultánea o sucesiva. Se comprueba además la partición literal de 150 combinaciones generadas con semilla fija.

```bash
.venv/bin/python -m pytest -q tests/asociacion/test_preservacion_textual.py tests/integracion/test_preservacion_textual.py tests/integracion/test_workflow.py
```

Las pruebas verifican el alcance de la lista de voces detectadas, el etiquetado, las referencias de minutas y su exclusión de evidencias ilocalizables, los visores y la reutilización de STT y diarización. Los modelos se sustituyen por entradas y respuestas de prueba; las salidas del modelo de minutas no constituyen una evaluación semántica. El notebook `stt_asr_peru.ipynb` admite segmentos sin intervalo; sus celdas de presentación se comprueban con datos sintéticos y se retiran las salidas antiguas, sin regenerarlas mediante inferencia.

En un entorno aislado con Python 3.13.5, `python -m compileall -q src tests evaluacion hito-2/scripts` terminó sin errores. La suite ordinaria (`python -m pytest -q -rs`) registró 768 pruebas y 52 subtests aprobados, 54 omisiones, seis deselecciones y dos fallos por ausencia de PyArrow en pruebas de Hito 2 (`test_auditoria_integrada_publica_datos_no_sensibles` y `test_tablas_csv_y_parquet_reales`). Las omisiones incluyen pruebas que requieren PySide6, eSpeak NG, 7-Zip, referencias RTTM, Whisper y el SDK de Ollama. En el entorno local con CUDA, la compilación terminó sin errores; las pruebas de asociación, STT, minutas e integración registraron 530 pruebas y 52 subtests aprobados. La suite ordinaria (`.venv/bin/python -m pytest -q -rs`) registró 861 pruebas y 52 subtests aprobados, una omisión por presencia de CUDA, seis deselecciones y ningún fallo. Queda pendiente la comprobación visual de la interfaz gráfica real. No se estima la frecuencia de estas condiciones en reuniones reales ni se modifican los resultados de evaluación previos.

## Límites y evaluación posterior

No consta una instalación nueva integral en CPU o Windows ni una evaluación completa en la RTX 3050 Laptop de 6 GB prevista por la definición de la PoC. El manifiesto de muestra de Hito 2 y el de Figshare no acreditan por sí solos que se haya congelado la muestra combinada específica de §2.3. La reunión consentida de evaluación, sus notas previas independientes, las muestras modulares concretas y los siete escenarios deben identificarse con sus propios hashes y registros. No se deben convertir ejecuciones cortas, resultados previos ni pruebas simuladas en un veredicto GO. Los umbrales y casos se deben tomar directamente del documento de Hito 3, sin crear una segunda definición normativa.
