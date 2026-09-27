# AI Opportunity Canvas — Propuesta 1: creación y mantenimiento de presentaciones técnicas

> **Equipo:** …  
> **Integrantes:** …  
> **Caso:** creación y mantenimiento asistido de presentaciones técnicas  
> **Versión:** 1 · **Fecha:** 2026-09-27

> **Estado:** canvas preliminar. Las afirmaciones que todavía no tienen validación con usuarios se mantienen explícitamente como hipótesis. La PoC no debería comenzar antes de medir una línea de base del flujo actual.

---

## 1. Problema y contexto

### A quién le pasa

A una persona que prepara **presentaciones técnicas o académicas de manera recurrente**, especialmente cuando el contenido ya existe en forma de notas, informes, resultados, ecuaciones, figuras o código, y va cambiando durante la preparación de la presentación.

El caso inicial se concentra en estudiantes de posgrado, investigadores, ingenieros, analistas y otros perfiles técnicos que producen sus propias presentaciones y necesitan conservar control fino sobre lo que muestran.

La circunstancia concreta es: **“ya sé qué quiero comunicar, pero todavía tengo que convertirlo en una presentación y mantenerla coherente mientras el contenido evoluciona”**.

### Qué le pasa

El progreso buscado no es simplemente “hacer una presentación”, sino **pasar de contenido e ideas ya elaboradas a una presentación lista para exponer, y poder revisarla repetidamente sin rehacer trabajo que no agrega contenido**.

- **Dimensión funcional:** organizar el contenido en una secuencia clara, convertirlo en diapositivas y mantener coherencia visual mientras cambian figuras, ecuaciones, resultados o mensajes.
- **Dimensión social:** presentar un trabajo que se perciba profesional, consistente y reconocible como propio o del equipo.
- **Dimensión emocional:** mantener sensación de control sobre el resultado y evitar la frustración de repetir ajustes de formato, alineación y composición cada vez que cambia algo.

Los obstáculos observados son:

- parte del contenido está estructurado conceptualmente, pero no visualmente;
- la composición exige decisiones y operaciones repetitivas de formato;
- una corrección local puede exigir reacomodar otros elementos;
- las figuras, resultados y ecuaciones pueden cambiar hasta etapas tardías;
- reutilizar una presentación anterior ayuda, pero también obliga a copiar, adaptar y corregir;
- una primera versión rápida no alcanza si después las modificaciones son difíciles de hacer con precisión o introducen cambios no deseados.

Una formulación compacta del problema es:

> **¿Cómo reducir el trabajo necesario para transformar contenido técnico en una presentación y mantenerla durante sucesivas revisiones, sin perder control, consistencia ni capacidad de intervención directa sobre el resultado?**

### Cuánto le cuesta

**Todavía no tenemos una línea de base propia y no conviene inventarla.** Éste es uno de los primeros datos que habría que medir.

Como evidencia secundaria de magnitud, el Work Trend Index de Microsoft reportó que los trabajadores observados en Microsoft 365 dedicaban el 43% de su tiempo en esas aplicaciones a creación en documentos, planillas y presentaciones, y un 8% del tiempo observado específicamente a PowerPoint [1]. Esto confirma que el trabajo de producción de presentaciones ocupa una fracción no trivial del trabajo de conocimiento, pero **no permite aislar cuánto corresponde a composición visual, cuánto a pensar el contenido ni cuánto podría ahorrarse**.

Para este caso, la línea de base debería obtenerse midiendo en usuarios reales:

- tiempo activo desde que el contenido está disponible hasta que la presentación se considera lista;
- tiempo dedicado a revisiones posteriores;
- cantidad de operaciones manuales de composición o reacomodamiento;
- cantidad de cambios repetidos sobre figuras, ecuaciones o resultados;
- cantidad de veces que una modificación local obliga a corregir otras partes.

### Evidencia

#### De confirmación

- El problema surge de una experiencia de uso real: producir presentaciones técnicas donde el contenido, las ecuaciones y las figuras cambian durante el trabajo y donde la edición final debe seguir bajo control del autor.
- Existe un mercado consolidado de herramientas específicas para acelerar la creación y edición de presentaciones, incluidas funciones generativas recientes de Anthropic, Microsoft, Google, Gamma y otras. Esto es evidencia de que el trabajo tiene valor suficiente como para que múltiples proveedores inviertan en reducirlo; **no demuestra por sí solo que nuestro encuadre particular esté desatendido** [2][3][4][5].
- Microsoft observa una participación significativa de PowerPoint dentro del tiempo de trabajo en Microsoft 365, aunque esa medición no descompone el tipo de esfuerzo [1].

#### De refutación

La hipótesis del problema se debilitaría si al entrevistar y observar usuarios encontramos que:

- el tiempo de composición y mantenimiento es pequeño frente al tiempo de decidir el contenido;
- las revisiones técnicas no generan retrabajo relevante;
- los usuarios ya están satisfechos con plantillas, herramientas actuales o asistentes de IA;
- la editabilidad y el control posterior no pesan en su decisión de herramienta;
- el problema sólo aparece en un conjunto demasiado pequeño o idiosincrático de usuarios.

**Validación pendiente:** entrevistar y observar al menos 5–10 personas que produzcan presentaciones técnicas recurrentemente y medir una línea de base sobre una tarea real.

---

## 2. Stakeholders

### Roles

| Papel | Quién es | Qué necesita ver para decir que sí |
|---|---|---|
| **Usuario** | Persona que prepara y mantiene la presentación: estudiante de posgrado, investigador, ingeniero, analista o perfil técnico similar. | Que reduzca trabajo real sin quitarle control; que pueda corregir el resultado y que los cambios no deseados sean escasos y reversibles. |
| **Influenciador** | Director, docente, coautor, compañero de equipo o responsable de comunicación que revisa la presentación. | Que la presentación respete el estilo, el contenido y las convenciones del grupo o institución. |
| **Recomendador** | Colega o referente técnico que ya usa un flujo similar y recomienda herramientas. | Que la herramienta funcione de manera consistente en casos reales y no obligue a adoptar un flujo frágil. |
| **Comprador** | En una adopción individual, el mismo usuario. En una organización, el equipo, laboratorio, empresa o institución. | Ahorro de tiempo suficiente para justificar costo y cambio de hábito. |
| **Decisor** | En la PoC individual, el propio usuario. En una organización, puede ser el responsable del equipo o de herramientas. | Compatibilidad con el flujo existente, seguridad de la información y beneficio observable. |
| **Saboteador** | No se identifica uno necesario para la PoC. En un contexto organizacional podría ser quien tenga que absorber retrabajo si la herramienta rompe plantillas, marca o procesos existentes. | Que la herramienta no aumente correcciones, riesgo ni mantenimiento. |

### Evidencia

#### De confirmación

- El usuario original del problema coincide con el usuario final y ya utiliza mecanismos de control directo para presentaciones técnicas, lo que es una señal de un **apaño existente** y no sólo de interés abstracto.
- Las herramientas actuales apuntan explícitamente tanto a usuarios individuales como a equipos que necesitan mantener marca, plantillas y estilos, lo que respalda la existencia de estos roles [2][3][5].

#### De refutación

- Todavía no verificamos si el comprador típico coincide con el usuario o si, fuera del caso individual, la decisión queda dominada por licencias institucionales ya existentes.
- Si la mayoría de los usuarios objetivo ya recibe PowerPoint, Copilot, Claude o Google Workspace por su organización y no pagaría ni cambiaría de herramienta, el espacio comercial se reduce significativamente.

---

## 3. Hipótesis de solución

### Descripción del producto

Se propone explorar un espacio de trabajo para **crear y modificar presentaciones a partir de contenido semiestructurado, presentaciones anteriores y nuevas instrucciones del usuario**, manteniendo una representación editable y controlada por éste.

El producto debería:

- transformar contenido e intención comunicacional en una primera estructura de presentación;
- reutilizar patrones observados en presentaciones anteriores del mismo usuario o equipo;
- conservar un perfil explícito y revisable de preferencias de comunicación y estilo;
- permitir modificaciones mediante instrucciones naturales;
- aplicar las modificaciones de manera localizada, evitando alterar partes no solicitadas;
- mantener separados el contenido, los recursos externos y las decisiones de composición;
- permitir que el usuario continúe editando el resultado sin depender del asistente;
- facilitar que una figura, ecuación o resultado actualizado pueda propagarse sin reconstruir manualmente la diapositiva.

La propuesta **no presupone todavía una tecnología final**. Una implementación posible podría usar una representación programática de las diapositivas, pero esa decisión debe competir contra alternativas más simples, incluida la posibilidad de construir una extensión o una habilidad sobre herramientas ya existentes.

### Acción

Cuando el usuario necesita crear o modificar una parte de la presentación, la acción que cambia es:

> **aplicar una transformación concreta y localizada sobre la presentación —crear, reorganizar, reemplazar o ajustar elementos— en lugar de que el usuario traduzca manualmente su intención a una secuencia de operaciones visuales.**

El usuario conserva la decisión de aceptar, corregir o revertir el resultado.

### Predicción

La parte que requiere inferencia es estimar, a partir de contenido incompleto y contexto previo:

- qué estructura de diapositiva expresa mejor la intención del usuario;
- qué información debe priorizarse visualmente;
- qué patrones de estilo y comunicación anteriores son relevantes para el caso actual;
- qué transformación concreta corresponde a una instrucción ambigua o de alto nivel;
- qué cambios pueden realizarse sin afectar contenido fuera del alcance solicitado.

El modelo no debería decidir cuestiones determinísticas que pueden resolverse mediante reglas o validaciones.

### Juicio

Los errores no tienen el mismo costo.

- **Es más costoso modificar contenido o elementos que el usuario no pidió tocar** que dejar una mejora estética sin hacer.
- **Es más costoso introducir una afirmación técnica, ecuación o dato incorrecto** que producir una diapositiva menos atractiva.
- La preservación de contenido, trazabilidad y editabilidad debe pesar más que la novedad visual.
- Cuando una modificación pueda cambiar el sentido técnico o el énfasis comunicacional, conviene pedir confirmación en lugar de decidir silenciosamente.

### Qué no necesita IA

Varias partes pueden y deberían resolverse de forma determinística:

- gestión de archivos y recursos;
- detección de referencias rotas;
- reemplazo de una figura por otra con la misma referencia;
- compilación o renderizado;
- validación de tamaños, desbordes y errores sintácticos;
- historial y reversión de cambios;
- aplicación de reglas explícitas de estilo.

La IA se justifica sólo donde hay que interpretar intención, contexto o preferencias no completamente especificadas.

### Evidencia

#### De confirmación

- La factibilidad general de generar y editar presentaciones mediante lenguaje natural ya está demostrada por productos actuales. Claude Slides permite crear presentaciones desde notas, archivos o conversaciones y editarlas directamente; Claude Design permite edición directa en lienzo y sistemas de diseño; Claude for PowerPoint edita dentro de PowerPoint; Copilot y Gemini también generan y modifican diapositivas [2][3][5][6][7].
- Las Skills de Claude demuestran que un modelo puede cargar instrucciones, scripts y recursos especializados de manera reutilizable, incluida la creación de PowerPoint y la aplicación de guías de marca [4].

#### De refutación

- La misma evidencia anterior reduce la novedad de la propuesta: **“generar diapositivas con IA y poder editarlas” ya no es una diferenciación suficiente**.
- Si una habilidad personalizada de Claude, un complemento de PowerPoint o Claude Slides resuelven el flujo con calidad comparable, construir un producto independiente no se justificaría.
- Si el perfil de preferencias aprendido no mejora de forma medible el resultado frente a una plantilla, un sistema de diseño o unos pocos ejemplos en contexto, esa parte del producto sobra.

---

## 4. Alternativas y statu quo

### Qué hace hoy el usuario

Un flujo habitual para una presentación técnica puede ser:

1. organizar contenido en notas, un informe, código, ecuaciones y figuras;
2. abrir una presentación anterior o una plantilla;
3. copiar y adaptar estructuras de diapositivas;
4. insertar contenido nuevo y ajustar manualmente jerarquía, tamaño, alineación y distribución;
5. corregir el resultado después de verlo completo;
6. ante cambios de resultados, ecuaciones o figuras, volver a la diapositiva afectada y repetir parte del trabajo;
7. si usa un asistente generativo, alternar entre pedir cambios y corregir manualmente lo que no quedó como esperaba.

El statu quo tiene una ventaja importante: **el usuario sabe cómo recuperar control**. Aunque sea lento, puede abrir el archivo y corregir exactamente lo que quiere.

### Qué otras soluciones existen o podrían aparecer

#### 1. Editores tradicionales

PowerPoint y Google Slides permiten control directo y son el estándar de facto en muchos entornos.

**Fortaleza:** control fino, colaboración y compatibilidad organizacional.  
**Debilidad para este caso:** gran parte de la traducción entre intención y composición sigue siendo manual.

#### 2. Presentaciones basadas en fuente

Beamer y Quarto permiten describir presentaciones como archivos de texto y regenerarlas de forma reproducible. Beamer separa contenido y apariencia mediante plantillas; Quarto puede generar presentaciones en Reveal.js, PowerPoint o Beamer y trabaja naturalmente con Markdown, ecuaciones y recursos externos [8][9].

**Fortaleza:** reproducibilidad, versionado, ecuaciones, recursos externos y control programático.  
**Debilidad:** el usuario sigue teniendo que expresar explícitamente buena parte de la estructura y composición; no incorporan por sí solos interpretación natural ni aprendizaje de preferencias.

#### 3. Claude Slides / Claude Design

A septiembre de 2026, las presentaciones tienen un punto de entrada propio en **Claude Slides**. Puede partir de notas, informes, archivos o conversaciones, permite editar diapositivas directamente o mediante conversación, usar sistemas de diseño y exportar a PowerPoint o PDF [2]. Claude Design, que inicialmente también cubría presentaciones, permite además edición directa en lienzo, comentarios, recursos de referencia y sistemas de diseño [3].

**Conclusión:** la observación hecha en clase sobre Claude Design era pertinente, pero el producto evolucionó rápidamente; hoy Claude Slides cubre de forma explícita buena parte de la generación y edición de presentaciones.

#### 4. Claude for PowerPoint + Skills

Es probablemente la alternativa más importante para esta propuesta.

Claude for PowerPoint puede crear diapositivas dentro de una plantilla, editar lo seleccionado y generar gráficos y diagramas nativos, preservando estilos y patrones de PowerPoint [5]. Las **Skills** son paquetes de instrucciones, scripts y recursos que Claude carga para tareas repetibles; Anthropic incluye una habilidad de PowerPoint y permite crear habilidades personalizadas para aplicar guías de estilo, plantillas y flujos propios [4].

Por lo tanto, la idea sugerida oralmente de “resolverlo con una skill” **es técnicamente plausible y debe tratarse como un sustituto real, no como una versión menor del problema**.

Lo que todavía habría que demostrar experimentalmente es si una skill satisface con igual calidad:

- adaptación progresiva a preferencias que emergen durante múltiples interacciones;
- mantenimiento de dependencias entre contenido técnico y presentación;
- trazabilidad de qué cambió y por qué;
- garantías de localidad de las modificaciones;
- portabilidad del artefacto fuera del proveedor.

No debe asumirse que no lo hace: hay que probarlo.

#### 5. Copilot, Gemini y generadores de presentaciones

Copilot en PowerPoint crea y edita contenido directamente en el archivo y puede seguir plantillas y kits de marca [6]. Gemini en Google Slides puede generar y editar diapositivas y reutilizar el estilo visual de presentaciones previas [7]. Gamma y otros generadores permiten crear, editar y exportar a PowerPoint; Gamma incluso conserva ciertos elementos como tablas editables en la exportación [10].

Estos productos hacen que el espacio competitivo sea un **mercado existente y muy activo**, no una categoría nueva.

### Por qué lo nuestro sería suficientemente mejor como para que alguien se mueva

Ésta es todavía una **hipótesis**, no una ventaja demostrada.

La propuesta sólo tendría sentido como producto diferenciado si consigue, en conjunto, algo que las alternativas no resuelvan suficientemente bien:

- **continuidad entre la fuente técnica y la presentación:** figuras, ecuaciones y resultados evolucionan sin reinserción manual;
- **fuente de verdad controlada por el usuario:** la presentación sigue siendo un artefacto explícito, versionable y editable fuera del asistente;
- **preferencias persistentes:** el sistema usa presentaciones anteriores y correcciones sucesivas para aprender cómo comunica el usuario, no sólo colores y tipografías;
- **ediciones localizadas y auditables:** una instrucción sobre una parte no debería modificar silenciosamente otras;
- **separación entre contenido e interpretación:** el sistema no debería inventar contenido técnico para completar un diseño.

Si estas ventajas no producen una mejora observable respecto de **Claude Slides / Claude for PowerPoint + una Skill**, la decisión correcta sería construir sobre esas plataformas o pivotar, no duplicarlas.

### Evidencia

#### De confirmación

- Beamer y Quarto confirman que existe valor en una representación textual, reproducible y desacoplada de los recursos [8][9].
- Claude Slides, Claude Design y los complementos de PowerPoint confirman que la interacción natural y la edición directa son técnicamente viables [2][3][5].
- Las Skills confirman que personalizar un flujo repetible con instrucciones, scripts y recursos es viable [4].

#### De refutación

- La competencia actual cubre mucho más del problema de lo que cubría cuando se formuló la idea original.
- Claude Slides ya acepta archivos previos, usa sistemas de diseño y permite edición directa; Claude for PowerPoint opera sobre el formato nativo [2][5].
- Una prueba en la que una Skill bien construida alcance tiempos, control y calidad similares al prototipo refutaría la necesidad de un producto independiente.

---

## 5. Hipótesis de datos

La PoC no requiere entrenar un modelo desde cero. El principal problema de datos es **disponer de suficiente contexto personal para inferir preferencias y de suficientes registros de uso para evaluar si esa inferencia sirve**.

### Dataset

| Dato | Origen | ¿Público? | ¿Lo vimos? | ¿Sensibles? | Sesgo conocido | Comentarios |
|---|---|---:|---:|---:|---|---|
| Contenido fuente de una nueva presentación | Usuario: notas, informe, Markdown, ecuaciones, figuras, resultados | No | Parcial | Puede ser | Refleja un único dominio o tipo de presentación | Es el insumo de cada tarea. |
| Presentaciones anteriores del mismo usuario/equipo | Archivos históricos | No | No como corpus consolidado | Puede ser | Muestran sólo estilos y contextos usados en el pasado | Base para inferir patrones de comunicación y estilo. |
| Recursos externos | Figuras, tablas, resultados, referencias | Mixto | Parcial | Puede ser | Puede haber recursos faltantes o generados por herramientas distintas | Importantes para validar actualización y trazabilidad. |
| Interacciones de edición | Instrucción del usuario + estado antes/después | No | Todavía no | Sí, en algunos casos | Las correcciones observadas dependen de la tarea y del momento | Deben empezar a registrarse desde el primer uso. |
| Aceptación/rechazo de cambios | Usuario | No | Todavía no | Bajo/medio | El usuario puede aceptar por cansancio o urgencia, no por preferencia estable | Conviene registrar también motivo o corrección posterior. |
| Versión final considerada “lista” | Usuario | No | Todavía no | Puede ser | La calidad es subjetiva y dependiente del público | Sirve como referencia para evaluar tiempo y retrabajo. |

### De dónde sale la respuesta correcta

No existe una única “diapositiva correcta” que permita plantear el problema como supervisado convencional.

Para evaluar preferencias y ediciones, la referencia más útil sería:

- qué propuesta aceptó el usuario;
- qué modificó manualmente después;
- qué revirtió;
- qué partes pidió mantener invariantes;
- cuál fue la versión final que consideró lista para presentar.

Esto permite construir pares o secuencias del tipo **estado inicial → instrucción → propuesta → corrección/aceptación**, más útiles que un conjunto estático de diapositivas “buenas”.

### Dato del que más depende el proyecto

El dato crítico no es una gran colección pública de presentaciones, sino **evidencia representativa de las preferencias de un mismo usuario a lo largo de varias presentaciones y revisiones**.

Si con pocas presentaciones anteriores y algunas correcciones no puede obtenerse una mejora consistente frente a una plantilla o un ejemplo en contexto, el componente de “perfil aprendido” pierde sentido.

### Evidencia

#### De confirmación

- El usuario objetivo ya dispone naturalmente de parte de los datos: presentaciones previas, archivos fuente y futuras correcciones.
- Las herramientas actuales permiten usar presentaciones previas, plantillas y sistemas de diseño como contexto, lo que indica que este tipo de dato es operacionalmente útil [2][3][5][7].

#### De refutación

- No se ha construido todavía un corpus real de varias personas con sus presentaciones, revisiones y preferencias.
- Las presentaciones previas pueden ser un mal predictor si el estilo cambia mucho según audiencia, materia o tipo de exposición.
- Si un único ejemplo reciente explica casi toda la preferencia útil, mantener un perfil longitudinal complejo sería innecesario.

---

## 6. Métrica de éxito

### Métrica de negocio

**Tiempo activo de edición humana desde que el contenido está listo hasta que el usuario considera la presentación lista para exponer.**

La comparación debe hacerse contra el **flujo que el usuario realmente elegiría hoy**, no sólo contra PowerPoint manual. Para usuarios avanzados puede ser Beamer/Quarto; para otros, Claude Slides, Copilot, Gemini o una combinación de herramientas.

La métrica de tiempo debe tener una condición de calidad: el ahorro no cuenta si el usuario termina con menor control, peor fidelidad técnica o una presentación que luego necesita rehacer.

### Umbral — por debajo de esto, no vale la pena

**Hipótesis inicial de decisión:** al menos **30% menos de tiempo activo** que el statu quo del mismo usuario, manteniendo igual o mejor valoración de control y calidad.

Este 30% **no está validado todavía**. Se deja escrito para evitar mover el objetivo después de construir, pero debería revisarse antes del desarrollo si la medición de línea de base o las entrevistas muestran que el costo de cambio exige otro umbral.

### Cómo se mediría dentro del trimestre

Prueba cruzada con aproximadamente **6–10 usuarios** que preparen presentaciones técnicas con regularidad:

1. cada participante aporta algunas presentaciones previas y un conjunto de contenido nuevo;
2. realiza una tarea comparable con su flujo habitual y otra con la PoC;
3. se contrabalancea el orden para reducir efecto de aprendizaje;
4. se mide tiempo activo, no tiempo de espera de compilación o generación;
5. al final, el usuario indica cuándo considera el resultado “listo para presentar” y puntúa control, fidelidad a su intención y necesidad de retrabajo.

Además de la creación inicial, se incluirían tareas de mantenimiento:

- reemplazar una figura por una nueva versión;
- cambiar una ecuación o resultado;
- dividir una diapositiva;
- dar más protagonismo a un elemento;
- aplicar una instrucción local sin modificar el resto.

### Métrica técnica que usaríamos como proxy

- porcentaje de instrucciones cumplidas sin corrección manual;
- tasa de modificaciones no solicitadas fuera del alcance indicado;
- tasa de renderizado/compilación correcta;
- cantidad de reversiones;
- consistencia con preferencias previamente confirmadas;
- tiempo de ejecución de cada edición.

La métrica técnica **no reemplaza** la métrica de producto.

### Qué se registra de cada uso

- estado de la presentación antes del cambio;
- instrucción del usuario;
- elementos afectados;
- cambio propuesto;
- aceptación, rechazo o edición manual posterior;
- tiempo activo de intervención;
- reversión, si la hubo;
- preferencia que el sistema creyó aplicar;
- confirmación o corrección de esa preferencia.

### Evidencia

#### De confirmación

- El tiempo activo puede medirse desde hoy sobre el flujo actual, sin construir el producto.
- Las alternativas actuales permiten montar un baseline exigente y realista, especialmente Claude Slides y Claude for PowerPoint + Skills [2][4][5].

#### De refutación

- Si no puede medirse con claridad cuándo una presentación está “lista”, la métrica se vuelve demasiado subjetiva.
- Si la PoC reduce tiempo pero aumenta la cantidad de correcciones no deseadas o reduce el control percibido, no resuelve el problema planteado.
- Si el flujo actual con una Skill o un asistente existente ya alcanza resultados similares, la mejora incremental puede no justificar el cambio.

---

## 7. Riesgos éticos y de sesgo (preliminar)

| Familia | Riesgo preliminar | Qué habría que observar |
|---|---|---|
| **Calidad de servicio** | El sistema puede funcionar mejor para usuarios con muchas presentaciones previas, estilos relativamente estables o contenido bien estructurado, y peor para quienes no tienen historial o cambian mucho de formato. | Resultados separados por cantidad de ejemplos previos, tipo de presentación y complejidad técnica. |
| **Representación** | Aprender de presentaciones anteriores puede cristalizar malos hábitos, volver homogéneo el estilo o asumir que una preferencia es universal cuando sólo valía para una audiencia. | Cambios de preferencia según contexto; capacidad del usuario de inspeccionar y corregir el perfil. |
| **Interpersonal / autonomía** | Una modificación automática puede alterar énfasis, mensaje o contenido sin que el autor lo advierta, reduciendo su control sobre lo que comunica. | Cambios fuera de alcance, reversiones y diferencias entre intención declarada y resultado. |
| **Privacidad** | Presentaciones técnicas pueden contener resultados inéditos, información de clientes, datos internos o recursos con restricciones. El historial de correcciones también puede revelar información del trabajo del usuario. | Qué datos salen del entorno del usuario, qué se conserva y bajo qué permisos. |
| **Social** | Si estos sistemas se usan masivamente, pueden homogeneizar la forma de comunicar y reducir habilidades de composición que antes permanecían en el autor. | Diversidad de resultados y dependencia del sistema a lo largo del tiempo. |

Un riesgo especialmente importante para este caso es la **invención de contenido técnico**. El sistema puede ser muy útil para decidir cómo representar algo sin ser una fuente válida para completar datos, ecuaciones o conclusiones ausentes. La PoC debería distinguir claramente entre **transformar contenido provisto** y **crear nuevas afirmaciones**.

No se identifica en principio un riesgo de asignación comparable con dominios como crédito, empleo o prestaciones públicas. El principal riesgo está en autonomía, privacidad, fidelidad técnica y calidad de servicio.

### Evidencia

#### De confirmación

- El propio problema de producto exige preservar control y cambios localizados; por lo tanto, la pérdida de autonomía no es un riesgo periférico sino una condición central de diseño.
- Los proveedores actuales enfatizan plantillas, sistemas de diseño y edición directa, señal de que consistencia y control son preocupaciones reales en este tipo de herramientas [2][3][5].

#### De refutación

- Si en la PoC se trabaja sólo con material propio/no sensible y todas las modificaciones son revisadas antes de cerrar la presentación, varios riesgos de privacidad e impacto interpersonal quedan acotados.
- Si se demuestra que el perfil de preferencias puede ser completamente explícito y editable, el riesgo de inferencias persistentes no controladas disminuye.

---

## Bitácora de revisiones

| Fecha | Sección | Qué cambió | Qué lo motivó |
|---|---|---|---|
| 2026-09-27 | Todo el canvas | La propuesta original se reencuadró según el AI Opportunity Canvas: problema separado de solución, acción/predicción/juicio, statu quo, datos, métrica y riesgos. | Consigna de Clase 02 y plantilla `2-ai-opportunity-canvas.md`. |
| 2026-09-27 | 4. Alternativas | Se incorporaron Claude Slides, Claude Design, Claude for PowerPoint, Skills, Copilot, Gemini, Gamma, Beamer y Quarto. | Investigación del estado actual de las alternativas. |
| 2026-09-27 | 3 y 4 | Se eliminó como diferenciación suficiente la idea de “IA pero editable”. | Claude Slides y las integraciones nativas ya permiten edición directa; Skills pueden encapsular flujos repetibles. |
| 2026-09-27 | 4 y 6 | La diferenciación pasó a depender de mantenimiento de contenido técnico, localidad de ediciones, fuente de verdad controlada por el usuario y preferencias persistentes. | Necesidad de competir contra alternativas actuales y no contra herramientas de una generación anterior. |

---

## Referencias y evidencia secundaria

1. Microsoft, *Will AI Fix Work? — Work Trend Index 2023*.  
   https://www.microsoft.com/en-us/worklab/work-trend-index/will-ai-fix-work

2. Anthropic, *Claude Artifacts / Claude Slides*.  
   https://claude.com/features/artifacts

3. Anthropic, *Get started with Claude Design* y anuncio de Claude Design.  
   https://support.claude.com/en/articles/14604416-get-started-with-claude-design  
   https://www.anthropic.com/news/claude-design-anthropic-labs

4. Anthropic, *What are Skills?* y *Use Skills in Claude*.  
   https://support.claude.com/en/articles/12512176-what-are-skills  
   https://support.claude.com/en/articles/12512180-use-skills-in-claude

5. Anthropic, *Claude for Microsoft 365*.  
   https://claude.com/claude-for-microsoft-365

6. Microsoft, *Edit with Copilot in PowerPoint*.  
   https://support.microsoft.com/en-us/powerpoint/edit-with-copilot-in-powerpoint

7. Google, *Generate slides with Gemini in Google Slides*.  
   https://support.google.com/docs/answer/16961475

8. Quarto, *Presentations*.  
   https://quarto.org/docs/presentations/

9. CTAN, *Beamer — A LaTeX class for producing presentations*.  
   https://ctan.org/tex-archive/macros/latex2e/contrib/beamer

10. Gamma, *What’s the easiest way to export my Gamma?*  
    https://help.gamma.app/en/articles/8022861-what-s-the-easiest-way-to-export-my-gamma

