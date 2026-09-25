# Problema

Las reuniones ocupan una parte cada vez mayor de la jornada laboral. Desde 2020, los usuarios de Teams tienen tres veces más reuniones y llamadas por semana, y más de la mitad de esas reuniones son llamadas improvisadas, sin agenda previa [1][2]. En cada una se toman decisiones, se reparten tareas y se asumen compromisos que después hay que recordar, comunicar y cumplir.

Dejar registro de lo que se decidió tiene un costo que suele pasar desapercibido. Quien coordina una reunión tiene que elegir entre participar de lleno o tomar notas: hacer las dos cosas bien al mismo tiempo es difícil. Como resultado, la minuta se escribe tarde, queda incompleta o directamente no se escribe. Los compromisos se pierden o se discuten después ("yo no dije eso"), y reconstruir quién se comprometió a qué termina dependiendo de la memoria.

Existen herramientas que resuelven esto automáticamente: asistentes que graban la reunión, la transcriben y generan un resumen. Sin embargo, en muchos contextos **no se pueden usar**:

* **Por confidencialidad:** la mayoría procesa el audio en servidores de terceros. En estudios jurídicos, equipos de salud, áreas financieras, organismos públicos o consultoras bajo acuerdos de confidencialidad, enviar lo que se dice en una reunión a un servicio externo no está permitido, o implica un riesgo que nadie quiere asumir.
* **Por la forma en que participan:** muchas se suman a la llamada como un participante más (el "bot" que aparece en la lista). Frente a un cliente, un paciente o una contraparte, eso resulta incómodo o directamente inaceptable.

Este problema no es hipotético. En 2025 se presentaron demandas colectivas contra dos de los asistentes más usados: una por grabar a participantes que no sabían que estaban siendo grabados [3], otra por generar huellas de voz sin consentimiento [4]. Asociaciones profesionales de abogados ya emitieron guías específicas advirtiendo sobre estos riesgos [5].

Existe entonces una tensión entre dos formas de trabajo:

* **Tomar notas a mano:** es privado y está bajo control, pero obliga a elegir entre participar y documentar.
* **Usar un asistente automático:** libera a quien participa, pero implica ceder el contenido de la reunión a un tercero y, muchas veces, sumar un participante artificial.

El problema puede sintetizarse entonces como:

**¿Cómo lograr que quien participa de una reunión obtenga un registro confiable de lo que se decidió, sin tener que tomar notas y sin que el contenido salga de su propia computadora?**

# Posible solución

Se propone explorar un asistente de reuniones que funcione **completamente de forma local**: graba la reunión desde la computadora del usuario, sin sumarse a la llamada como participante, y al finalizar genera la transcripción y una minuta estructurada utilizando modelos que corren en la misma máquina, sin conexión a servicios externos.

## Flujo general

**grabación → transcripción → identificación de hablantes → confirmación del usuario → minuta → revisión → exportación**

El procesamiento ocurre después de la reunión, no en vivo. Esto reduce los requisitos de hardware y es una concesión razonable: el usuario no necesita la minuta durante la reunión, sino minutos después de terminarla.

## Componentes principales

* **Captura en dos canales:** en reuniones virtuales se graban por separado el micrófono del usuario y el audio del sistema (el resto de los participantes). Esto permite saber, sin necesidad de ningún modelo, qué dijo el propio usuario.
* **Transcripción:** conversión del audio a texto con marcas de tiempo, mediante un modelo de reconocimiento de voz local (por ejemplo, Whisper).
* **Identificación de hablantes:** separación de quién habló en cada momento (por ejemplo, con pyannote). El sistema distingue voces, pero no sabe quién es quién: **el usuario asigna los nombres** al revisar.
* **Minuta estructurada:** un modelo de lenguaje local extrae temas, decisiones, compromisos (quién, qué, para cuándo) y preguntas abiertas.
* **Análisis de oratoria del propio usuario:** tiempo de habla, velocidad, muletillas, interrupciones y monólogos largos.
* **Interfaz de revisión:** el usuario confirma hablantes, corrige la minuta y la exporta.

## Minuta con respaldo

Una propiedad central de la propuesta es que **cada ítem de la minuta esté vinculado al fragmento de la transcripción que lo respalda**. Si el modelo no puede señalar dónde se dijo algo, ese ítem no aparece.

Esto responde a un riesgo concreto: los modelos de reconocimiento de voz pueden inventar frases que nunca se dijeron. En el caso de Whisper, se observó en alrededor del 1% de las transcripciones analizadas [6]. En una minuta, un compromiso inventado es mucho más grave que uno omitido: el omitido se agrega a mano, mientras que el inventado se envía por mail y genera un conflicto.

Por el mismo motivo, cuando el sistema no puede determinar con confianza quién dijo algo, debería indicarlo como "hablante no identificado" en lugar de adivinar. La identificación automática de hablantes tiene tasas de error cercanas al 20% incluso en condiciones de laboratorio [7].

## Análisis de oratoria

El análisis de oratoria se limita **al propio usuario**, que es quien eligió usar la herramienta. La mayoría de estas métricas no requieren inteligencia artificial: palabras por minuto, proporción de tiempo hablado, solapamientos o duración de los turnos se calculan a partir de las marcas de tiempo de la transcripción.

Una dificultad técnica a tener en cuenta: Whisper tiende a "limpiar" la transcripción y omitir muletillas como "eh", "este" u "o sea". Para contarlas hace falta un modelo de transcripción literal, como CrisperWhisper [8].

## Qué queda fuera

Inicialmente se había considerado incluir **análisis de sentimiento de los participantes**. Se propone dejarlo fuera, por dos motivos:

* **Regulatorio:** la Ley de IA de la Unión Europea prohíbe, desde febrero de 2025, los sistemas que infieren emociones de personas en el ámbito laboral a partir de datos biométricos, como la voz [9].
* **Ético:** analizar el estado emocional de colegas que no eligieron usar la herramienta se parece más a la vigilancia que a la asistencia.

Si se quisiera explorar algo parecido, sería textual y agregado por tema ("en este punto hubo desacuerdo"), nunca por persona.

## Consentimiento

Que la herramienta no aparezca en la llamada no significa que se pueda grabar sin avisar. En Argentina, el Código Civil y Comercial exige consentimiento para captar la voz de una persona (art. 53) [10]. Por eso el aviso a los participantes debería ser parte del producto: un texto para compartir al inicio de la reunión, un indicador visible de grabación y el borrado del audio una vez generada la minuta.

Tampoco deberían guardarse huellas de voz para reconocer automáticamente a las personas entre reuniones: esa funcionalidad fue justamente la que motivó una de las demandas mencionadas [4].

# Alternativas existentes

* **Asistentes en la nube con bot** (Otter, Fireflies, Fathom, tl;dv): son el estándar, pero justamente lo que no se puede usar en contextos confidenciales.
* **Asistentes integrados en la plataforma** (Copilot en Teams, Gemini en Meet): no suman un bot y procesan los datos dentro del entorno del proveedor [11]. Son la alternativa más fuerte para organizaciones que ya pagan esas licencias.
* **Asistentes sin bot, pero en la nube** (Granola, Jamie): resuelven la incomodidad del bot, pero no la confidencialidad.
* **Herramientas locales de código abierto:** Meetily graba y resume localmente [12]; noScribe transcribe e identifica hablantes, pero no genera minutas [13].

La existencia de herramientas locales confirma que hay interés en el problema, pero obliga a definir qué aportaría esta propuesta: **identificación de hablantes con confirmación del usuario, minutas con respaldo verificable, evaluación en castellano rioplatense y consentimiento incorporado al diseño**. Una alternativa a considerar es construir sobre Meetily, que es de código abierto, en lugar de empezar desde cero.

# Aspectos de inteligencia artificial involucrados

La propuesta permite abordar distintos problemas propios de sistemas basados en inteligencia artificial:

* reconocimiento automático del habla en castellano conversacional;
* identificación de hablantes (diarización);
* extracción estructurada de información a partir de texto;
* generación de resúmenes con un modelo de lenguaje local;
* verificación de que lo generado esté respaldado por la fuente;
* ejecución de modelos con recursos limitados (una laptop, sin GPU dedicada);
* evaluación de sesgos: los sistemas de reconocimiento de voz funcionan peor con algunos acentos, variedades del castellano y grupos de hablantes [14][15].

# Datos

No se propone entrenar modelos desde cero, sino utilizar modelos preentrenados y evaluarlos. El dato más importante es entonces un **conjunto de evaluación**: reuniones con su transcripción de referencia, los hablantes identificados y una minuta escrita por una persona.

Existen corpus públicos de reuniones en inglés que incluyen resúmenes con decisiones y acciones (AMI [16], ELITR [17]), pero **no se encontró ningún corpus público de reuniones en castellano**, y menos en variedad rioplatense. Una parte del trabajo consistiría en construirlo, por ejemplo grabando reuniones del propio equipo con consentimiento de sus integrantes.

# Posibles criterios de evaluación

El criterio principal sería de uso: **cuánto tiempo pasa desde que termina la reunión hasta que la minuta está lista para enviar**, incluyendo la revisión del usuario, comparado con escribirla a mano.

Algunas métricas posibles son:

* tiempo de revisión y corrección de la minuta;
* cantidad de compromisos o decisiones inventados (idealmente, ninguno);
* cantidad de compromisos o decisiones omitidos;
* errores en la atribución de lo dicho a cada participante;
* calidad de la transcripción en castellano (tasa de error por palabra);
* tiempo de procesamiento de una reunión de una hora en una laptop común;
* diferencias de calidad entre hablantes, acentos y condiciones de audio.

También podrían compararse distintas configuraciones: modelos de distinto tamaño, con o sin verificación de respaldo, o contra una herramienta local existente como Meetily.

# Síntesis

El problema no consiste simplemente en transcribir reuniones automáticamente, sino en **permitir que una persona participe plenamente de una reunión y obtenga un registro confiable de lo que se decidió, en contextos donde ceder ese contenido a un tercero no es una opción**.

La solución propuesta explora un asistente que funciona completamente en la computadora del usuario, que genera minutas donde cada afirmación puede rastrearse hasta lo que efectivamente se dijo, y que incorpora el consentimiento de los participantes como parte de su diseño.

El principio central puede sintetizarse como:

**el registro de una reunión debería quedar en manos de quienes participaron de ella, y cada cosa que afirme debería poder verificarse contra lo que realmente se dijo.**

---

## Referencias

1. Microsoft, *Work Trend Index 2023* — https://www.microsoft.com/en-us/worklab/work-trend-index/will-ai-fix-work
2. Microsoft, *Breaking down the infinite workday* (2025) — https://www.microsoft.com/en-us/worklab/work-trend-index/breaking-down-infinite-workday
3. *Brewer v. Otter.ai* (2025) — https://www.npr.org/2025/08/15/g-s1-83087/otter-ai-transcription-class-action-lawsuit
4. *Cruz v. Fireflies.AI Corp.* (2025) — https://www.ebglaw.com/insights/publications/ai-meeting-assistants-and-biometric-privacy-lessons-from-the-fireflies-ai-lawsuit
5. NYC Bar Association, *Formal Opinion 2025-6* — https://www.nycbar.org/reports/formal-opinion-2025-6-ethical-issues-affecting-use-of-ai-to-record-transcribe-and-summarize-conversations-with-clients/
6. Koenecke et al., *Careless Whisper: Speech-to-Text Hallucination Harms*, FAccT 2024 — https://arxiv.org/abs/2402.08021
7. pyannote, *speaker-diarization-community-1* — https://huggingface.co/pyannote/speaker-diarization-community-1
8. CrisperWhisper — https://github.com/nyrahealth/CrisperWhisper
9. FPF, *Red Lines under EU AI Act: emotion recognition in the workplace* — https://fpf.org/blog/red-lines-under-eu-ai-act-unpacking-the-prohibition-of-emotion-recognition-in-the-workplace-and-education-institutions/
10. La Nación, *¿Qué pasa en las empresas cuando un empleado graba a un compañero o a un jefe?* — https://www.lanacion.com.ar/economia/que-pasa-en-las-empresas-cuando-un-empleado-graba-a-un-companero-o-a-un-jefe-nid2026642/
11. Microsoft Learn, *Data, Privacy, and Security for Microsoft 365 Copilot* — https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-privacy
12. Meetily — https://github.com/Zackriya-Solutions/meetily
13. noScribe — https://github.com/kaixxx/noScribe
14. Koenecke et al., *Racial disparities in automated speech recognition*, PNAS 2020 — https://www.pnas.org/doi/10.1073/pnas.1915768117
15. Jimenez & Kern, *Dialect and Gender Bias in YouTube's Spanish Captioning System* (2026) — https://arxiv.org/abs/2602.24002
16. AMI Meeting Corpus — https://groups.inf.ed.ac.uk/ami/corpus/
17. ELITR Minuting Corpus — https://aclanthology.org/2022.lrec-1.340/
