# Niveles que el producto necesita

**Revisión 4 · 2026-10-12.** Alcance: producto en **castellano**, evaluado **por módulo**.

Ningún umbral cambia. Los niveles de transcripción, separación de hablantes y
de punta a punta son los de la revisión 1 (escrita antes de descargar datos);
M1 a M3 son los de la revisión 3. La revisión 4 solo asigna cada nivel a un
módulo y vuelve el idioma a castellano.

| Id | Módulo | Propiedad | Nivel | De dónde sale |
|---|---|---|---|---|
| V1 | Transcripción | Volumen | ≥ 3 h y ≥ 30 hablantes en castellano rioplatense | Medir el error por palabra con ±1 punto, sin depender de pocas voces |
| V2 | Transcripción | Volumen · habla espontánea | ≥ 1 h (~9.000 palabras) | El producto transcribe reuniones, no lectura |
| C1 | Transcripción | Completitud | Transcripción en ≥ 99% de los audios | Sin referencia no se mide el error |
| C5 | Transcripción | Completitud · datos demográficos | Género, edad y acento en ≥ 70% de los clips de una fuente | Medir calidad de servicio por grupo |
| K1 | Transcripción | Corrección · duplicados | ≤ 1% | Inflan el volumen y contaminan la partición |
| K3 | Transcripción | Corrección · audio | ≥ 99% legible y con la duración declarada | Un audio roto es un caso perdido |
| K4 | Transcripción | Corrección · texto | ≤ 1% con caracteres ajenos al castellano, después de normalizar por reglas | La métrica compara texto contra texto |
| G1 | Transcripción | Vigencia | ≥ 80% de las horas de 2015 en adelante | Vocabulario y grabación actuales |
| R1 | Transcripción | Representatividad · género | Ningún género bajo el 30% | Usuarios ~50/50 |
| R2 | Transcripción | Representatividad · edad | ≥ 50% de hablantes de 30 años o más | Profesionales en actividad |
| R3 | Transcripción | Representatividad · estilo | ≥ 50% de las horas de habla espontánea | Una reunión no es lectura |
| F1 | Transcripción | Confiabilidad | 100% transcripto o validado por personas | No se evalúa un modelo contra otro |
| F3 | Transcripción | Confiabilidad · error de la referencia | ≤ 2% de desacuerdo entre dos transcriptores del equipo | Menor que el error que se quiere medir |
| V3 | Separación de hablantes | Volumen | ≥ 20 sesiones y ≥ 3 h con turnos con tiempos | El error varía mucho entre sesiones |
| C2 | Separación de hablantes | Completitud | Hablante en ≥ 95% de los turnos | Cada frase se atribuye a una persona |
| K2 | Separación de hablantes | Corrección · tiempos | 0 turnos con fin ≤ inicio | Invalidan la métrica |
| G2 | Separación de hablantes | Vigencia · modalidad | Al menos una fuente de videollamada | El producto graba reuniones virtuales |
| R4 | Separación de hablantes | Representatividad · tamaño | ≥ 50% de las sesiones con 3 a 8 hablantes | Reunión típica del producto |
| R6 | Separación de hablantes | Representatividad · reuniones reales | ≥ 30% de las horas de reuniones no actuadas | Una reunión actuada no es igual a una real |
| M1 | Minuta | Volumen | ≥ 10 reuniones con resumen, decisiones y acciones de referencia | Comparar la minuta generada contra una referencia |
| M2 | Minuta | Representatividad · reuniones reales | ≥ 30% de las horas con minuta son de reuniones no actuadas | Igual criterio que R6 |
| M3 | Minuta | Confiabilidad · juez | El juez (LLM) coincide con la anotación humana en ≥ 80% de los ítems (κ de Cohen ≥ 0,6) | Un juez sin calibrar no mide nada |
| C4 | Minuta | Completitud · evidencia | ≥ 80% de las decisiones y acciones enlazadas a un fragmento de la transcripción | El producto exige una cita por ítem |
| R5 | Minuta | Representatividad · idioma | ≥ 30 reuniones con minuta de referencia en castellano | El producto entrega minutas en castellano |
| V5 | De punta a punta | Volumen | ≥ 10 reuniones en castellano de ≥ 20 min con audio, transcripción, hablantes y minuta | El umbral del canvas no se evalúa con menos de 10 |
