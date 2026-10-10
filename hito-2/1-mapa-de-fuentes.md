# Mapa de fuentes

**Documento 1 de 4 del [Hito 2](README.md)**

**Equipo:** Luisa, Bruno, Matías, Felipe.

**Alcance:** reuniones en inglés; transcribir y separar hablantes.

**El dato del que más depende el proyecto:** reuniones en inglés con audio,
transcripción y hablantes con tiempos. Lo tienen AMI e ICSI.

---

## 1. Fuentes evaluadas

| # | Fuente | Origen | ¿Disponible hoy? | Complejidad de obtención | Sensible / licencia | Volumen |
|---|---|---|---|---|---|---|
| 1 | **AMI Meeting Corpus** | Terceros (Univ. de Edimburgo) | Sí. Matías, 10/10 | Anotaciones: 23 MB. Audio: 11,5 GB, descarga directa por reunión | CC BY 4.0. Voces de voluntarios | 171 reuniones, 100,0 h |
| 2 | **ICSI Meeting Corpus** | Terceros (ICSI Berkeley) | Sí. Matías, 10/10 | Anotaciones: 55 MB. Audio: 8,3 GB, descarga directa por reunión | CC BY 4.0 | 75 reuniones, 71,7 h |
| 3 | **VoxConverse** | Terceros (Univ. de Oxford) | Sí. Matías, 10/10 | Tiempos: 0,3 MB. Audio: 6,3 GB en dos zips | CC BY 4.0. Videos de YouTube | 448 sesiones, 63,5 h. Sin transcripción |
| 4 | **Reuniones propias** en inglés, por videollamada | Usuario (el equipo) | No existe | ~18 h de trabajo: grabar 5 reuniones y transcribirlas | Voces del equipo; consentimiento escrito | Objetivo: 5 reuniones, 2,5 h |

Descartadas por alcance (castellano, portugués o sin relación con las dos
etapas): OpenSLR 61, CORdeBA, Humyn LATAM, Common Voice.

## 2. Riesgos anticipados por propiedad

| # | Completitud | Corrección | Vigencia | Representatividad | Confiabilidad |
|---|---|---|---|---|---|
| 1 | Que falte audio de alguna reunión anotada | Tiempos incompletos en algunas reuniones (lo avisa la documentación) | 2004–2005 | Reuniones actuadas; muchos hablantes no nativos | Transcripción manual; tiempos por alineación automática |
| 2 | No sabemos | No sabemos | ~2000 | Grupos de investigación | Transcripción manual |
| 3 | Sin transcripción | No sabemos | 2020 | No son reuniones | Tiempos automáticos corregidos a mano |
| 4 | Depende del equipo | Depende del equipo | Actual | Solo 4 personas | Doble transcripción |

## 3. Plan de obtención

| # | Quién | Para cuándo |
|---|---|---|
| 1, 2, 3 | Matías | 10/10 — hecho |
| 4 | Equipo | Antes de congelar el conjunto de evaluación |

## 4. Resultado de la obtención

| # | Qué se obtuvo | En la muestra | Qué cambió respecto de lo esperado |
|---|---|---|---|
| 1 | Transcripción, hablantes y tiempos de las 171 reuniones; índice del audio de las 171; 16 extractos de 30 s | Sí | Las 171 tienen audio. La duración que declaran los metadatos no coincide con el audio en el 20% de las reuniones. 40 de 190 hablantes no tienen datos demográficos |
| 2 | Ídem para las 75 reuniones; 8 extractos | Sí | Las 75 tienen audio. El 11,5% de las palabras no tiene tiempo |
| 3 | Tiempos de las 448 sesiones | Sí | pyannote lo usa para entrenar: no sirve como evaluación principal |
| 4 | — | No | — |
