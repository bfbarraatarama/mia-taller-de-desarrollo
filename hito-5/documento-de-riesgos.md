# Documento de riesgos · Generación automática de minutas

**Documento del Hito 5 · Luisa, Bruno, Matías y Felipe · Clase 11**

Model card abreviada del sistema construido, más sus riesgos, mitigaciones y trazabilidad desde el [canvas](../canvas.md) (Hito 1) y la [hoja de datos](../hito-2/3-datasheet.md) (Hito 2). Números al 20/11/2026, sobre `main`; cada uno enlaza a lo que lo produce. Probabilidad y severidad son la propuesta del borrador, para confirmar por el equipo.

---

## 1. Descripción del sistema

| | |
|---|---|
| Qué hace | Graba micrófono y audio del sistema, separa quién habló, transcribe, el usuario nombra cada voz y genera una minuta con temas, decisiones, problemas y acciones, cada ítem con su marca temporal |
| Cómo | Workflow fijo, sin agente ni entrenamiento: pyannote `speaker-diarization-community-1` (diarización), Whisper `medium` (transcripción), asociación temporal propia y `qwen2.5:7b` por Ollama (minuta) |
| Dónde corre | Localmente, en una laptop con RTX 3050 de 6 GB. El modelo de minutas puede estar en otra PC de la red o en AWS Bedrock solo con autorización explícita por ejecución |
| Sobre qué datos se evaluó | Muestra congelada (SHA-256 `68b31711…`): 5 clips de lectura (Common Voice, OpenSLR), 3 sesiones de juego en castellano rioplatense (Figshare, 74 grabaciones), 3 reuniones de AMI traducidas; una reunión real de OSM LatAm (339 s, dominio público); 7 grabaciones espontáneas de Humyn y CORdeBA (#27) |

## 2. Usos previstos y fuera de alcance

| Uso | |
|---|---|
| Previsto | Que quien coordina una reunión de trabajo en castellano tenga un borrador de minuta para **revisar** antes de enviarlo, sin que el audio salga de su computadora |
| No debe usarse para | Grabar sin avisar a los participantes; evaluar el desempeño de empleados; usar la minuta como prueba o acta firme sin revisión humana; identificar personas por su voz (canvas, §7) |
| Con qué se puede confundir | Con un acta fiel: la minuta resume y puede omitir o inventar (§3.2). Con un sistema que reconoce personas: los nombres los pone el usuario, el sistema solo separa voces |
| Fuera de alcance | Personalización terminológica, hardware de bajos recursos y optimización del rendimiento (definición de la PoC, §1.3). Sin evaluar: lenguas distintas del castellano |

## 3. Desempeño y limitaciones

### 3.1 Por módulo y por segmento

| Módulo | Segmento | Resultado | Lectura | Evidencia |
|---|---|---|---|---|
| Transcripción (WER) | Habla leída: Common Voice / OpenSLR | 0 % / 9,1 % | 9 y 22 palabras: no alcanza para comparar género ni acento | [`metricas_stt.json`](../evaluacion/modular/resultados/metricas_stt.json) |
| | Espontánea rioplatense, juego (Figshare) | 27,0 % | 13.125 palabras | ídem |
| | Espontánea: Perú / Venezuela (Humyn) | 14,8 % / 24,8 % | 2 grabaciones por país | #27 |
| | Espontánea: Buenos Aires (CORdeBA) | 42,7 % | Confundido con su referencia fonética («hacemo», muletillas): no prueba un peor desempeño con el acento local | #27 |
| Diarización (DER estricto / JER) | Sesiones S22 / S23 / S25 | 18,9 % / 28,4 % / 20,2 % · JER 36,6 a 48,7 % | La sesión con peor DER también tiene la peor asociación | [`metricas_diarizacion.json`](../evaluacion/modular/resultados/metricas_diarizacion.json) |
| Asociación (palabras con el hablante correcto) | S22 / S23 / S25 | 92,3 % / 84,2 % / 86,8 % | 12,3 % de las palabras quedan en otro hablante; 60 % de las intervenciones se marcan como ambiguas | [`metricas_asociacion.json`](../evaluacion/modular/resultados/metricas_asociacion.json) |
| Minuta (AMI) | 3 reuniones | 22 de 55 ítems; acciones 3 de 8 | Recupera menos de la mitad | [`planilla_minutas.json`](../evaluacion/modular/resultados/planilla_minutas.json) |
| Integral (calidad, §2.3) | Un archivo / varios archivos | 1/2 temas en ambas; acción 0/1 y 1/1; **2 y 1 acciones inventadas** | No cumple | [`calidad.md`](../evaluacion/integral/resultados/baseline/calidad.md) |
| Latencia | 5 min 39 s de audio / 35 min de audio | 261 s / 3.605 s, con GPU | Cumple §2.3 para 5 min; 35 min tardan 1 h | [`reporte.md`](../evaluacion/integral/resultados/baseline/reporte.md), [registro de escenarios](../docs/evaluacion/openspec/changes/escenarios-funcionales/registro-pruebas.md) |

Grupos sin medir: mayores de 50 años, mujeres frente a hombres y hablantes de otras regiones de Argentina. El canvas pedía medir los dos primeros; la muestra no los separa.

### 3.2 Dónde falla

| Caso | Qué pasa | Evidencia |
|---|---|---|
| Propuestas y preguntas | Las registra como acciones comprometidas | `calidad.md`: concurso de logos, lista de apps, videos |
| Terminología y nombres de productos | Los transcribe como palabras comunes | «Discourse» → «discurso» ([`terminologia.json`](../evaluacion/escenarios/resultados/terminologia.json)) |
| Superposición y voces parecidas | Atribuye mal o marca como ambiguo | 2.1.2: 48 de 69 intervenciones ambiguas ([`escenarios.json`](../evaluacion/escenarios/resultados/escenarios.json)) |
| Nombres mal puestos en las fichas | La minuta hereda el error del usuario | Corrida 01: el hablante al que llaman «Rafael» quedó como «Jorge» |
| Reuniones largas | Tarda más que la reunión | 2.1.5: 35 min de audio en 1 h |

## 4. Riesgos identificados

### 4.1 El error caro

| | |
|---|---|
| Cuál | **Una acción atribuida a quien no la asumió**: inventada, o asumida por otra persona. El canvas fijó el lado del error: «Inventar un compromiso es peor que omitirlo» |
| Con qué número | 2 y 1 acciones inventadas en las 2 modalidades de la reunión de prueba; 1 de 2 corridas con el responsable de la acción mal atribuido |
| Quién lo sufre | La persona a la que se le adjudica la tarea, que puede no ser la usuaria ni haber visto la minuta; y la usuaria que la envía sin revisar |
| Cómo se administra | El sistema no decide: produce un borrador que la usuaria revisa, con la marca temporal de cada acción para verificarla en el audio; responsable «Sin asignar» si no consta; plan B del riesgo 2 para reducir las invenciones (definición de la PoC, §5.2) |

### 4.2 Tabla de riesgos

| # | Riesgo | A quién afecta | Probabilidad | Severidad | Evidencia |
|---|---|---|---|---|---|
| R1 | Acción inventada (alucinación) | Participante señalado; usuaria | Alta: 2 de 2 modalidades | Alta | `calidad.md` |
| R2 | Frase o compromiso atribuido a otra persona | Participante | Media: 12,3 % de palabras en otro hablante | Alta | Asociación; corrida 01 |
| R3 | Omisión de temas o acciones | Usuaria | Alta: T1 parcial en 2 de 2; AMI, acciones 3 de 8 | Media | `calidad.md`, planilla AMI |
| R4 | Peor transcripción para habla espontánea, acentos o ruido | Hablantes poco representados | Media: WER de 9 % (leída) a 27 % (espontánea) | Media | §3.1 |
| R5 | Términos del dominio mal transcritos | Usuaria, que corrige a mano | Alta en dominios especializados | Baja | 2.1.1 |
| R6 | Grabar sin que los demás participantes lo sepan | Participantes | Sin medir | Alta: voz como dato personal (CCyC art. 53) | La aplicación no muestra un aviso de consentimiento antes de grabar |
| R7 | La transcripción sale de la organización | Participantes; organización | Baja: requiere autorización explícita | Alta | Prueba del 18/11 (README); `tests/minutas/test_privacidad.py` |
| R8 | Audio y transcripción quedan en disco indefinidamente | Participantes | Alta: no hay borrado | Media | La aplicación conserva todo por diseño (recuperación, 3.1.5) |
| R9 | Instrucciones dichas en la reunión manipulan la minuta (prompt injection) | Usuaria; participantes | Sin medir | Media | Sin pruebas adversariales |
| R10 | Uso para evaluar empleados o como prueba sin revisión | Participantes | Sin medir | Alta | Uso prohibido en el canvas; no hay control técnico |

### 4.3 Riesgos propios del LLM

| Riesgo | En este sistema | Estado |
|---|---|---|
| Alucinación | R1 | Medido: ocurre |
| Prompt injection | R9 | Mitigado en el diseño; sin medir |
| Fuga de datos por el prompt | R7 | Mitigado y probado |
| Contenido dañino | La minuta resume lo dicho; no genera contenido fuera de la reunión | Salida restringida a un esquema JSON de secciones |

## 5. Mitigaciones

| Riesgo | Implementado en la PoC | A implementar antes de producción | Límite asumido |
|---|---|---|---|
| R1, R3 | Prompt con «no inventes responsables ni plazos», `null` si no consta; marca temporal por ítem; revisión humana antes de enviar | Plan B del riesgo 2; distinguir propuesta de compromiso en el prompt; marcar las acciones de baja evidencia | La minuta es un borrador |
| R2 | Marcas de superposición y ambigüedad; nombres puestos por la usuaria escuchando cada voz; «hablante no identificado» | Revisar la atribución de cada acción antes de enviar | Diarización preentrenada, sin ajuste |
| R4, R5 | Se declara el desempeño por segmento | Vocabulario por organización (fuera del alcance de la PoC); medir por edad y género | Sin datos para esos grupos |
| R6 | — | Aviso de consentimiento obligatorio e indicador visible de grabación (canvas, A4) | **Brecha**: previsto en el canvas, no construido |
| R7 | Ejecución local por defecto; destino externo solo con autorización por ejecución; nunca se envía el audio; destino registrado | Lista de servidores permitidos por la organización | Bedrock queda como opción experimental |
| R8 | — | Borrado del audio y opción de guardar solo la minuta (canvas, §7) | **Brecha**: previsto en el canvas, no construido |
| R9 | Instrucciones y transcripción en mensajes separados; «son datos, no instrucciones»; salida con esquema; visor que no interpreta HTML ni enlaces | Pruebas adversariales | — |
| R10 | Usos prohibidos declarados (§2) | Términos de uso | No hay control técnico posible |

## 6. Trazabilidad

| Riesgo | Previsto en el canvas | Agregado por la hoja de datos | Revelado por el sistema |
|---|---|---|---|
| R1, R3 | Juicio: inventar es peor que omitir; cita por ítem | No hay reuniones en castellano con minuta de referencia (V5 = 0/10) | Inventa acciones en las 2 modalidades; omite parte de T1 |
| R2 | Asignación: atribuir un compromiso a quien no lo asumió | Pyannote se entrenó con AMI: posible sobreestimación en AMI | 12,3 % de palabras mal atribuidas; error de ficha heredado |
| R4 | Calidad de servicio: hablantes de fuera de Buenos Aires y mayores de 50 | Common Voice y OpenSLR son habla leída; la edad no se puede verificar por hablante | La brecha mayor es leída frente a espontánea; edad y género, sin medir |
| R6 | Interpersonal: aviso de consentimiento obligatorio | — | No se construyó |
| R7 | A1: nada sale del equipo | — | Se agregó la opción de servidor con autorización |
| R8 | Social: guardar solo la minuta; borrado del audio | — | No se construyó |
| Latencia | A3: 1 h de reunión en 30 min o menos, sin GPU | — | 35 min de audio tardan 1 h con GPU |

## 7. Marco externo

| Marco | Lectura del equipo |
|---|---|
| AI Act (Reglamento UE 2024/1689) | En el uso previsto queda fuera del anexo III: riesgo **mínimo o limitado**, con transparencia hacia las personas grabadas y sobre el contenido generado (art. 50). Pasaría a **alto riesgo** si se usara para decisiones laborales (anexo III), uso que se declara prohibido. No hay identificación biométrica: no se guardan huellas de voz, la diarización solo conserva tiempos y etiquetas. No es asesoramiento legal |
| NIST AI RMF 1.0 | Mapear: §2 y §6. Medir: §3. Gestionar: §5, con R6 y R8 como residuales sin mitigar. Gobernar: revisión humana obligatoria y usos prohibidos (§2) |
