# Mapa de fuentes

**Documento 1 de 4 del [Hito 2](README.md)**

**Equipo:** Luisa, Bruno, Matías, Felipe.

**Alcance:** producto en castellano, evaluado por módulo.

**El dato del que más depende el proyecto:** reuniones en castellano con
audio, transcripción, hablantes y minuta. No existe en ninguna fuente
pública: cada módulo se evalúa con su propia fuente, y el producto completo,
con reuniones propias.

---

## 1. Fuentes evaluadas

| # | Módulo | Fuente | Origen | ¿Disponible hoy? | Complejidad | Sensible / licencia | Volumen |
|---|---|---|---|---|---|---|---|
| 1 | Transcripción | **OpenSLR 61** (rioplatense, leído) | Terceros (Google) | Sí. Matías, 10/10 | 1,75 GB; servidor lento (25 min) | CC BY-SA 4.0. Voces anónimas | 5.739 clips, 8,0 h, 44 hablantes |
| 2 | Transcripción | **CORdeBA** (Buenos Aires, espontáneo) | Terceros (UNLP) | Sí. Matías, 10/10 | 348 MB | **CC BY-NC-SA 4.0** (no comercial). Conversaciones privadas | 24 grabaciones, 6,4 h. Sin tiempos |
| 3 | Transcripción y hablantes | **Humyn LATAM** (espontáneo, con tiempos) | Terceros (proveedor comercial) | Sí. Matías, 10/10 | 1,0 GB | CC BY 4.0 | 6 grabaciones en castellano; 2 argentinas (31 min) |
| 4 | Transcripción | **Common Voice 26 rioplatense** (leído) | Terceros (Mozilla) | No: pide cuenta | Cuenta gratuita + 427 MB | CC0 | ~16 h según su ficha |
| 5 | Hablantes y minuta | **AMI Meeting Corpus** (inglés) | Terceros (Univ. de Edimburgo) | Sí. Matías, 10/10 | Anotaciones 23 MB; audio 11,5 GB por reunión | CC BY 4.0 | 171 reuniones, 100,0 h; 142 con minuta |
| 6 | Hablantes | **ICSI Meeting Corpus** (inglés) | Terceros (ICSI Berkeley) | Sí. Matías, 10/10 | Anotaciones 55 MB; audio 8,3 GB | CC BY 4.0 | 75 reuniones, 71,7 h |
| 7 | Hablantes | **VoxConverse** (inglés) | Terceros (Univ. de Oxford) | Sí. Matías, 10/10 | Tiempos 0,3 MB; audio 6,3 GB | CC BY 4.0 | 448 sesiones, 63,5 h |
| 8 | Minuta | **AMI traducido al castellano** (transcripción y minuta) | Sintético, derivado de 5 | No existe | Traducir 142 reuniones y revisar una muestra | Hereda CC BY 4.0 | 142 reuniones |
| 9 | De punta a punta | **Reuniones propias** en castellano | Usuario (el equipo) | No existe | ~35 h: grabar 10, transcribir, anotar minuta y evidencias | Voces del equipo; consentimiento escrito | Objetivo: 10 reuniones, 5 h |

## 2. Riesgos anticipados por propiedad

| # | Completitud | Corrección | Vigencia | Representatividad | Confiabilidad |
|---|---|---|---|---|---|
| 1 | No sabemos | "Puede haber errores" (ficha) | 2018–2019 | Lectura; solo Buenos Aires | Control manual |
| 2 | Hablantes sí, tiempos no | Marcas de oralidad en el texto | 2014–2019 | Hablantes jóvenes | Docentes de la UNLP |
| 3 | No sabemos | No sabemos | Reciente | Esperábamos más material argentino | Proveedor comercial |
| 4 | Edad y género optativos | Validación por votos | 2026 | Lectura | Voluntarios |
| 5 | Que no todas tengan minuta | Tiempos incompletos en algunas | 2004–2005 | Inglés; reuniones actuadas | Anotadores con guía |
| 6 | No sabemos | No sabemos | ~2000 | Inglés; grupos de investigación | Transcripción manual |
| 7 | Sin transcripción | No sabemos | 2020 | No son reuniones | Automático, corregido a mano |
| 8 | La del original | Errores de traducción | La del original | Castellano de traductor | Depende del traductor |
| 9 | Depende del equipo | Depende del equipo | Actual | 4 personas | Doble anotación |

## 3. Plan de obtención

| # | Quién | Para cuándo |
|---|---|---|
| 1, 2, 3, 5, 6, 7 | Matías | 10/10 — hecho |
| 4 | Responsable de transcripción | Módulo 4 |
| 8 | Responsable de minuta | Módulo 4 |
| 9 | Equipo | Antes de congelar el conjunto de evaluación |

## 4. Resultado de la obtención

| # | Qué se obtuvo | En la muestra | Qué cambió respecto de lo esperado |
|---|---|---|---|
| 1 | Todo | Transcripciones e índice del audio | 70% de las horas son de mujeres. El 83% de los clips lee una oración que lee otro hablante |
| 2 | Todo | Índice y turnos | 1 audio no abre; 3 transcripciones sin separar por hablante |
| 3 | Todo | Índice y turnos en castellano | El texto cubre el 71% del audio. 20 de las 28 filas no son lo que dice la ficha |
| 4 | Nada | No | — |
| 5 | Turnos, participantes, índice de audio, minutas y sus enlaces a la transcripción | Sí | Las 171 tienen audio. 138 de las 142 minutas son de reuniones actuadas. 47 "ítems" son el marcador `*NA*` |
| 6 | Turnos, hablantes, índice de audio | Sí | Las 75 tienen audio |
| 7 | Tiempos de las 448 sesiones | Sí | pyannote lo usa para entrenar |
| 8, 9 | — | No | — |
