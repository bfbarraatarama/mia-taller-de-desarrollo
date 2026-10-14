# Plan de evaluación tecnológica para la generación automática de minutas

## Objetivo

Evaluar alternativas tecnológicas para construir un flujo de trabajo que capture el audio de reuniones, identifique los turnos de habla, transcriba las intervenciones y genere minutas estructuradas. Primero se compararán las herramientas por módulo y luego se validará el flujo completo con reuniones propias en español.

## Workflow propuesto

1. **Captura de audio** → archivo de audio de la reunión.
2. **Diarización** → segmentos temporales asociados a hablantes.
3. **Transcripción (ASR)** → texto con marcas temporales, vinculado con los hablantes.
4. **Generación de minuta** → síntesis estructurada de la reunión.
5. **Validación integral** → prueba del workflow completo con reuniones propias.

> La diarización y la transcripción se evaluarán inicialmente por separado para distinguir sus errores; posteriormente se integrarán mediante las marcas temporales.

## Paso 1. Captura de audio

**Objetivo:** grabar tanto el audio del sistema como el del micrófono local. Cuando sea posible, conservar fuentes o pistas separadas.

| Alternativa | Ventajas | Limitaciones |
|---|---|---|
| **Python + sounddevice** | Integración directa con Python; automatización y control de canales. | La captura de audio del sistema depende de los dispositivos, controladores y sistema operativo; puede requerir loopback o un dispositivo virtual. |
| **Audacity** | Gratuito y de código abierto; permite visualizar y comprobar las fuentes grabadas. | Requiere configuración de dispositivos. En Linux puede usarse PipeWire; en Windows, loopback o cables virtuales, según el equipo. |
| **OBS Studio + FFmpeg** | OBS es gratuito y de código abierto; puede capturar micrófono y audio del sistema en pistas separadas. FFmpeg permite extraer o convertir el audio. | Mayor configuración y archivos potencialmente más grandes si se graba video (incluso con pantalla negra). |

**Entrada:** fuentes de micrófono y audio del sistema.

**Salida recomendada:** WAV PCM, preferentemente a 16 kHz para el procesamiento posterior, manteniendo una copia de las pistas originales. Si se graban fuentes separadas, conservarlas antes de mezclar a mono.

**Pruebas:** verificar que ambas fuentes se registren, que no haya pérdidas o desincronización y que el audio pueda procesarse en los módulos siguientes.

## Paso 2. Diarización

**Objetivo:** identificar **quién habló y cuándo**, asignando etiquetas de hablante sin necesidad de conocer su identidad real.

| Alternativa | Ventajas | Limitaciones |
|---|---|---|
| **pyannote.audio (Python)** | Integración con Python; modelos preentrenados; salidas con intervalos por hablante. | Algunos modelos requieren autorización o aceptación de condiciones de acceso; el rendimiento puede depender de GPU y de la configuración. |
| **NVIDIA NeMo** | Framework con modelos y pipelines de diarización; permite configuraciones avanzadas. | Instalación y ajustes más complejos; requisitos de hardware variables. |
| **Kaldi (núcleo C++)** | Herramientas acústicas flexibles y consolidadas. | Mayor esfuerzo de integración, preparación de datos y mantenimiento. |

**Entrada:** audio WAV, adaptado a los requisitos del pipeline elegido.

**Salida:** RTTM o JSON con inicio, fin y etiqueta de hablante. Ejemplo:

```json
[
  {"start": 0.0, "end": 4.5, "speaker": "SPEAKER_00"},
  {"start": 4.7, "end": 8.2, "speaker": "SPEAKER_01"}
]
```

**Métricas:**

- **DER (Diarization Error Rate):** errores de asignación de hablante, habla omitida y falsas detecciones de habla.
- **JER (Jaccard Error Rate):** desacuerdo temporal entre los segmentos de referencia y los detectados por hablante.

**Criterio:** menor DER y JER implica mejor desempeño. Es necesario disponer de anotaciones de referencia con tiempos y hablantes. Se deberá fijar una misma configuración de evaluación (por ejemplo, tratamiento del solapamiento y tolerancia en los límites de segmento) para comparar las herramientas.

## Paso 3. Transcripción de audio a texto (ASR)

**Objetivo:** obtener el contenido textual de las intervenciones y marcas temporales que permitan asociarlas con la diarización.

| Alternativa | Ventajas | Limitaciones |
|---|---|---|
| **OpenAI Whisper (local)** | Modelos descargables; soporte multilingüe, incluido español; ejecución local. | Consumo de recursos; posibles errores con nombres propios, tecnicismos y superposición de voces. |
| **NVIDIA NeMo (local)** | Modelos ASR ejecutables localmente; opciones de personalización. | Requiere elegir un modelo adecuado para el idioma y configurar el entorno. |
| **ElevenLabs Scribe v2 (API)** | Integración mediante API; servicio de transcripción administrado. | Dependencia de servicio externo, límites de uso y envío del audio a la nube. |

**Entrada:** audio en un formato compatible con cada alternativa.

**Salida recomendada:** JSON con texto y marcas temporales. Luego de integrar la diarización, agregar el identificador de hablante.

```json
[
  {"start": 0.0, "end": 4.5, "speaker": "SPEAKER_00", "text": "Revisamos los avances del proyecto."}
]
```

**Métricas:**

- **WER (Word Error Rate):** `WER = (S + D + I) / N`, donde `S` = sustituciones, `D` = eliminaciones, `I` = inserciones y `N` = cantidad de palabras de la referencia.
- **RTF (Real-Time Factor):** `RTF = tiempo de procesamiento / duración del audio`. Un RTF menor que 1 indica procesamiento más rápido que tiempo real.

**Criterio:** comparar sobre los mismos audios y transcripciones de referencia corregidas manualmente. Documentar idioma, modelo, hardware y configuración.

## Paso 4. De transcripción a minuta

**Objetivo:** convertir la transcripción identificada por hablantes en una minuta que resuma temas, decisiones, responsables y acciones pendientes, sin inventar información.

| Alternativa | Ventajas | Limitaciones |
|---|---|---|
| **LLM local** | Mayor control de los datos; puede ejecutarse sin enviar contenido a servicios externos. | Limitado por los recursos de cómputo y las capacidades del modelo elegido. |
| **API de AWS** | Acceso a modelos administrados; posibilidad de utilizar créditos disponibles. | Requiere cuenta, permisos y configuración; cuotas y consumo de créditos. |
| **Groq Cloud** | Inferencia rápida; disponibilidad de planes gratuitos con límites para determinados modelos. | Restricciones de uso variables y procesamiento en la nube. |

**Entrada:** transcripción estructurada con hablantes y marcas temporales.

**Salida:** minuta en Markdown o JSON con una estructura común.

**Estrategia de prueba:**

1. Tomar la estructura de minuta disponible en el corpus **AMI** como referencia.
2. Traducir al español las transcripciones seleccionadas de AMI, conservando el significado de decisiones, tareas y responsables.
3. Ejecutar las mismas transcripciones y el mismo prompt en las alternativas elegidas.
4. Comparar las minutas generadas con la referencia y realizar una revisión humana.

**Criterios de evaluación propuestos:** cobertura de temas relevantes, fidelidad de decisiones, identificación de tareas y responsables, ausencia de información inventada, cumplimiento de la estructura y claridad de redacción.

> Las minutas de referencia no necesariamente son la única síntesis válida. La comparación automática debe complementarse con revisión humana.

### Evaluación de la calidad de la minuta generada

**Objetivo:** comparar la minuta generada por cada LLM con una minuta de referencia, utilizando el mismo contenido de entrada y una estructura común. Se proponen tres métodos complementarios.

#### Método 1. LLM-as-a-Judge (evaluación global)

Se utiliza un LLM evaluador para comparar la minuta generada con la minuta de referencia y, cuando corresponda, con la transcripción original.

**Criterios sugeridos:**

- **Cobertura:** ¿incluye los temas, decisiones y acciones importantes?
- **Fidelidad:** ¿representa correctamente lo discutido, sin cambiar el sentido?
- **Ausencia de invenciones:** ¿evita agregar decisiones, tareas o responsables que no aparecen en la fuente?
- **Estructura:** ¿respeta las secciones y el formato de minuta definido a partir de AMI?
- **Claridad:** ¿la redacción es comprensible, concisa y útil?

**Salida propuesta:** un JSON con puntajes por criterio (por ejemplo, de 0 a 5), una justificación breve y evidencia textual. La escala y la rúbrica deben fijarse antes de comparar herramientas. Conviene utilizar el mismo juez, prompt y configuración para todas las alternativas, y revisar manualmente una muestra para detectar sesgos del evaluador.

#### Método 2. Cobertura ítem por ítem de la minuta de referencia

En lugar de comparar únicamente dos documentos completos, se descompone la minuta real/de referencia en **ítems verificables**: temas relevantes, decisiones, acciones, responsables y fechas o compromisos.

Para cada ítem, se pregunta al LLM Judge: **«¿Está esta información contenida en la minuta generada, aunque esté expresada con otras palabras?»**

**Procedimiento:**

1. Extraer y enumerar los ítems de la minuta de referencia; idealmente, revisarlos manualmente.
2. Proporcionar al juez un ítem por vez junto con la minuta generada.
3. Solicitar una clasificación: **1 = presente y correcto; 0,5 = parcialmente presente; 0 = ausente o incorrecto**, acompañada de una cita justificativa.
4. Calcular la cobertura promedio sobre todos los ítems de referencia:

   `Cobertura (%) = 100 × suma(puntajes de ítems) / número de ítems`

5. Desglosar el resultado por tipo de información (temas, decisiones, acciones, responsables).

**Ejemplo:** si una minuta de referencia contiene 10 ítems y la suma de puntajes es 8,5, la cobertura es **85 %**.

**Limitación importante:** esta métrica mide principalmente omisiones. Una minuta podría cubrir todos los ítems y, aun así, incluir afirmaciones inventadas. Por eso se propone una verificación adicional, en sentido inverso: identificar afirmaciones de la minuta generada que no estén respaldadas por la transcripción o la referencia, distinguiendo información adicional válida de invenciones. Los ítems críticos pueden analizarse por separado o ponderarse, pero los pesos deben definirse de antemano.

#### Método 3. Similitud semántica mediante embeddings y coseno

Se genera un vector de embedding para la minuta de referencia y otro para la minuta producida, utilizando **el mismo modelo de embeddings**. Luego se calcula:

`Similitud coseno = (embedding_referencia · embedding_generada) / (||embedding_referencia|| × ||embedding_generada||)`

**Interpretación:** valores mayores indican que los textos tienen representaciones semánticas más cercanas. La escala práctica y los umbrales dependen del modelo; no se debe asumir un valor universal de aprobación.

**Ventajas:** cálculo automático, reproducible y rápido; tolera diferencias de redacción y vocabulario.

**Limitaciones:** una similitud elevada no garantiza que estén presentes todas las decisiones, fechas o responsabilidades; puede ocultar contradicciones u omisiones. También puede verse afectada por la longitud y la estructura de los textos.

**Recomendación:** calcular la similitud global y, si las secciones son comparables, también por sección (temas, decisiones, tareas). No utilizar el coseno como único indicador de calidad.

#### Comparación y selección

| Método | Qué mide principalmente | Resultado propuesto | Principal limitación |
|---|---|---|---|
| LLM-as-a-Judge global | Calidad, fidelidad y formato | Puntaje por criterio (0–5) | Subjetividad y sesgo del juez |
| Judge ítem por ítem | Cobertura de información de referencia | Porcentaje de cobertura y desglose por categoría | No detecta por sí solo todas las invenciones |
| Embeddings + coseno | Cercanía semántica general | Similitud coseno | No asegura exactitud factual ni cobertura de detalles |

**Diseño de prueba:** utilizar las mismas transcripciones, minutas de referencia y estructura para todos los LLM candidatos. En AMI, revisar la traducción al español y la alineación entre transcripción y minuta de referencia. Registrar resultados por reunión, no sólo un promedio global. Complementar las métricas automáticas con revisión humana de una muestra de minutas.

## Paso 5. Validación integral del workflow

**Objetivo:** comprobar que los módulos seleccionados funcionen de forma conjunta en reuniones reales del equipo, grabadas en español.

**Secuencia:**

1. Grabar una reunión propia.
2. Ejecutar diarización sobre el audio.
3. Ejecutar ASR e integrar texto, tiempos y hablantes.
4. Generar la minuta con la alternativa LLM seleccionada.
5. Revisar el resultado frente al contenido real de la reunión.

**Aspectos a observar:** funcionamiento de extremo a extremo, coherencia de hablantes, calidad de transcripción, fidelidad de la minuta, errores acumulados entre módulos y tiempo total de procesamiento.

**Consideración metodológica:** las pruebas con AMI permiten comparar resultados con referencias existentes. Las reuniones propias en español permiten verificar la aplicabilidad al caso real. Traducir una transcripción de AMI no sustituye la evaluación del ASR sobre audio originalmente hablado en español.

## Fuera del alcance

- **Ruido ambiental / relación señal-ruido (SNR):** no se realizarán experimentos específicos para medir robustez ante distintos niveles de ruido.
- **Precio:** no se utilizará el costo como métrica de comparación. Sí se registrarán las restricciones prácticas de créditos, cuotas, límites de uso y requisitos de acceso.

## Entregables esperados

- Comparativa de ventajas y limitaciones por etapa.
- Resultados de DER y JER para diarización.
- Resultados de WER y RTF para transcripción.
- Evaluación de calidad de las minutas generadas mediante LLM-as-a-Judge, cobertura ítem por ítem y similitud coseno de embeddings.
- Selección justificada de una alternativa por módulo.
- Workflow integrado y probado con reuniones propias en español.
