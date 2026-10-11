# Niveles que el producto necesita

**Revisión 3 · 2026-10-11.** Alcance: reuniones en inglés; transcribir, separar hablantes y generar la minuta (esta última, solo con AMI).

Los umbrales V, C, K, G, R y F son los de la revisión 2, sin cambios. La
revisión 3 agrega los niveles M1 a M3 de la minuta. Esos tres se escribieron
después de inspeccionar qué anotaciones de resumen trae AMI (cuántas
reuniones, no su contenido) y antes de correr ninguna celda que los mida.
M1 se cumple de antemano por esa inspección y M2 probablemente no; se
declaran igual.

La revisión 2 (2026-10-10) había cambiado el idioma, quitado los niveles de la
minuta y reescrito V5 y R6 para el alcance de entonces, sin tocar ningún
umbral. Se escribió antes de abrir ningún audio.

| Id | Propiedad | Nivel | De dónde sale |
|---|---|---|---|
| V1 | Volumen · transcripción en inglés | ≥ 3 h y ≥ 30 hablantes distintos | Para medir la tasa de error por palabra con ±1 punto y que no dependa de pocas voces |
| V2 | Volumen · transcripción de habla espontánea | ≥ 1 h (~9.000 palabras) | El producto transcribe reuniones, no lectura |
| V3 | Volumen · separación de hablantes | ≥ 20 sesiones y ≥ 3 h con turnos con tiempos | El error de diarización varía mucho entre sesiones; hacen falta varias para promediar |
| V5 | Volumen · las dos etapas juntas (audio → transcripción con hablantes) | ≥ 10 reuniones de ≥ 20 min con audio disponible, transcripción y hablantes con tiempos | Para medir el error que combina palabra y hablante sobre reuniones enteras |
| C1 | Completitud · transcripción | Presente en ≥ 99% de los audios | Sin referencia no se puede medir el error |
| C2 | Completitud · hablante | Presente en ≥ 95% de los turnos | La transcripción atribuye cada frase a una persona |
| C5 | Completitud · datos demográficos | Género, edad y acento en ≥ 70% de los hablantes de al menos una fuente | Para medir calidad de servicio por grupo (canvas §7) |
| K1 | Corrección · duplicados exactos | ≤ 1% | Inflan el volumen y contaminan la partición |
| K2 | Corrección · tiempos | 0 turnos con fin ≤ inicio o tiempos negativos | Invalidan la métrica de diarización |
| K3 | Corrección · audio | ≥ 99% de los archivos legibles y con la duración declarada | Un audio roto es un caso perdido |
| K4 | Corrección · texto | ≤ 1% de las transcripciones con caracteres ajenos al idioma, después de una normalización por reglas | La métrica compara texto contra texto |
| G1 | Vigencia · habla | ≥ 80% de las horas grabadas de 2015 en adelante | Vocabulario y condiciones de grabación actuales |
| G2 | Vigencia · modalidad | Al menos una fuente con audio de videollamada (posterior a 2020) | El producto graba reuniones virtuales |
| R1 | Representatividad · género | Ningún género declarado por debajo del 30% | Los usuarios son ~50/50 |
| R2 | Representatividad · edad | ≥ 50% del material de hablantes de 30 años o más | Los usuarios son profesionales en actividad |
| R3 | Representatividad · estilo | ≥ 50% de las horas de habla espontánea | Una reunión no es lectura |
| R4 | Representatividad · tamaño de la reunión | ≥ 50% de las sesiones con 3 a 8 hablantes | Reunión típica del producto |
| R6 | Representatividad · reuniones reales | ≥ 30% de las horas de reuniones no actuadas | Una reunión actuada no se parece del todo a una real |
| F1 | Confiabilidad · transcripción | 100% hecha o validada por personas, con procedimiento documentado | No se evalúa un modelo contra otro modelo |
| F3 | Confiabilidad · error de la referencia | ≤ 2% de palabras en desacuerdo entre dos personas del equipo que transcriben por separado la misma muestra chica | Por debajo del error que queremos medir en el sistema |
| M1 | Volumen · minuta de referencia | ≥ 10 reuniones con resumen, decisiones y acciones de referencia | Para comparar la minuta generada contra una referencia en varias reuniones y series |
| M2 | Representatividad · minuta de reuniones reales | ≥ 30% de las horas de reuniones con minuta de referencia son de reuniones no actuadas | Una reunión actuada no se parece del todo a una real (igual criterio que R6) |
| M3 | Confiabilidad · juez de la minuta | El juez (LLM) coincide con la anotación humana en ≥ 80% de los ítems de una muestra etiquetada por el equipo (κ de Cohen ≥ 0,6) | Un juez sin calibrar no mide nada |
