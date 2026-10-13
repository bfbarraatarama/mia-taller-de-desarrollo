# EDA de viabilidad

**Documento 2 de 4 del [Hito 2](README.md)**

**Equipo:** Luisa, Bruno, Matías, Felipe.

**Muestra:** [`hito-2/muestra/`](muestra/) · **Notebook:** [`hito-2/notebooks/eda_viabilidad.ipynb`](notebooks/eda_viabilidad.ipynb)

**Alcance:** producto en castellano, evaluado por módulo. Los datos son el
conjunto de evaluación: no se entrena ningún modelo.

**Resultado:** 25 niveles fijados antes de analizar las fuentes, sin modificar sus umbrales. Los resultados consolidados y las cinco búsquedas de *leakage* se calculan en el notebook (`[ACTUALIZACION]`) y se exportan a `resultados_eda.csv` y `resultados_leakage.csv`. Las mediciones históricas se conservan donde siguen siendo pertinentes; las limitaciones de las nuevas fuentes se indican explícitamente. «Celda» identifica la medición original en el notebook, complementada por `[ACTUALIZACION]`.

| Módulo | Sí | No | En parte | Pendiente |
|---|---|---|---|---|
| Transcripción (castellano) | 5 | 2 | 3 | 3 |
| Separación de hablantes | 4 | 2 | 0 | 0 |
| Minuta | 2 | 2 | 0 | 1 |
| De punta a punta | 0 | 1 | 0 | 0 |

---

## Evidencia complementaria obtenida

La preparación común conserva **16.156 instancias ASR** (10.393 Common Voice, 5.739 OpenSLR 61, 24 CORdeBA) y **49.492 segmentos de diarización** (28.110 CALLHOME, 21.382 Figshare), junto con 359 registros de grabación y 374 identificadores locales de hablante. Las cinco tablas pasaron el contrato estructural sin incidencias y se verificaron por SHA-256. Estos identificadores **no equivalen a 374 personas distintas**.

La auditoría acústica decodificó **105 de 106 archivos seleccionados**: Common Voice 30/30 MP3 originales, OpenSLR 44/44 clips FLAC derivados, CORdeBA 7/8 originales, Figshare 9/9 mezclas de inspección de 30 segundos y CALLHOME 15/15 audios embebidos. Las tasas muestrales no estiman la calidad de todos los originales; las mezclas Figshare no sustituyen los 219 pares completos.

En CALLHOME se documentaron **dos intervalos inválidos de 28.112** originales. Además, **dos de 15 registros con audio inspeccionado** tienen anotaciones cuyo extremo excede materialmente la duración del audio (187,73 y 260,12 segundos); es un problema diferente del intervalo con fin menor o igual al inicio. Por lo tanto, superar la validación estructural no implica que sus intervalos sean puntuables. En Figshare se aceptan discrepancias terminales de hasta 10 ms sin alterar las anotaciones: 213 de 219 pares requirieron esa tolerancia, y el exceso máximo fue 9,875 ms.

Common Voice presenta los tres metadatos (edad, género y acento) en el **97,5%** de 10.393 clips: faltan edad en 139, género en 261 y acento en 0. Se identificaron **0 colaboradores compartidos entre splits de origen** y **0 repeticiones colaborador/oración** entre colaboradores con identificador; ninguna de estas verificaciones demuestra ausencia de duplicados acústicos o exposición previa a preentrenamiento. La edad está medida por *clip*, no por persona; no se da por cumplido R2 sin esa distinción. En los 15 audios CALLHOME inspeccionados, **159 de 3.168 segmentos** exceden el audio por más de 10 ms, correspondientes a **2 de 15 registros**. Ningún dato faltante se imputa.

## 1. Requerimientos: el nivel que el producto necesita

Fijados en [`niveles-a-priori.md`](niveles-a-priori.md), por módulo.

| Propiedad | Nivel que el producto necesita | De dónde sale |
|---|---|---|
| Volumen | **V1** ≥ 3 h y ≥ 30 hablantes en castellano. **V2** ≥ 1 h espontánea. **V3** ≥ 20 sesiones y ≥ 3 h con hablantes y tiempos. **M1** ≥ 10 reuniones con minuta completa. **V5** ≥ 10 reuniones en castellano con todo | Medir cada módulo con margen de error acotado; el umbral del canvas necesita 10 reuniones |
| Completitud | **C1** transcripción en ≥ 99% de los audios. **C2** hablante en ≥ 95% de los turnos. **C4** ≥ 80% de decisiones y acciones con evidencia. **C5** género, edad y acento en ≥ 70% de una fuente | Canvas §3 y §7 |
| Corrección | **K1** duplicados ≤ 1%. **K2** cero turnos inválidos. **K3** ≥ 99% de audios legibles. **K4** ≤ 1% de textos con caracteres ajenos | Las métricas comparan texto y tiempos |
| Vigencia | **G1** ≥ 80% de las horas desde 2015. **G2** una fuente de videollamada | El producto graba reuniones virtuales |
| Representatividad | **R1** ningún género bajo 30%. **R2** ≥ 50% de 30 años o más. **R3** ≥ 50% espontáneo. **R4** ≥ 50% de sesiones con 3 a 8 hablantes. **R5** ≥ 30 minutas en castellano. **R6**, **M2** ≥ 30% de horas de reuniones reales | Canvas §1 |
| Confiabilidad | **F1** transcripción hecha por personas. **F3** ≤ 2% de desacuerdo entre dos transcriptores. **M3** juez LLM de acuerdo con humanos en ≥ 80% (κ ≥ 0,6) | La referencia tiene que ser más confiable que lo que se mide |

## 2. Resultados de la verificación

### Transcripción (castellano rioplatense)

Fuentes históricas: OpenSLR 61 (leído), CORdeBA (espontáneo, sin tiempos), Humyn LATAM · Argentina (espontáneo, con tiempos). Fuente complementaria adquirida: Common Voice 26 Rioplatense (leído; sus horas totales aún no fueron medidas).

| Id | Medido o estimado | Resultado | Celda | Si es estimado, procedencia | Cumple |
|---|---|---|---|---|---|
| V1 | Medido | 15,0 h y 44 hablantes (OpenSLR 61 8,0 h; CORdeBA 6,4 h; Humyn Argentina 0,52 h) | `V1` | — | Sí |
| V2 | Medido | 58.076 palabras espontáneas (54.577 de CORdeBA, sin tiempos; 3.499 de Humyn, con tiempos) | `V2` | — | Sí |
| C1 | Medido | OpenSLR 61: 100,0%. Humyn: el texto cubre 71,4% del audio. CORdeBA: sin tiempos; 3 de 23 grabaciones bajo 100 palabras/min | `C1` | — | **En parte** |
| C5 | Medido | Common Voice: **97,5%** de 10.393 clips con edad, género y acento simultáneamente (faltantes: 139, 261 y 0). Las fuentes históricas no reunían los tres metadatos. | `C5` + `[ACTUALIZACION]` | — | **Sí** |
| K1 | Medido | 1,4%: 78 de 5.739 clips repiten hablante y oración | `K1` | — | **No**: se deja uno de cada par |
| K3 | Medido | OpenSLR 61: 100,0% de 5.739. CORdeBA: 23 de 24. Humyn: 100,0% | `K3` | — | **En parte** |
| K4 | Medido | 0,0% (OpenSLR 61), 0,4% (Humyn), 0,0% (CORdeBA). 26,3% de los turnos de CORdeBA trae marcas de solapamiento, que la regla quita | `K4` | — | Sí |
| G1 | Estimado | Entre 53,6% y 92,8% de las horas desde 2015 | `G1` | Fichas: OpenSLR 61 2018–2019; CORdeBA 2014–2019 | Pendiente |
| R1 | Medido | OpenSLR 61: 69,9% de las horas de mujeres y 30,1% de varones. Common Voice: 7.486 clips `male_masculine`, 2.646 `female_feminine`, 261 sin género; **no** son porcentajes por horas ni por hablantes. | `R1` + `[ACTUALIZACION]` | — | Sí (OpenSLR) |
| R2 | Medido por clip; no resuelto por hablante | Common Voice declara edad por clip (139 sin dato), pero la distribución por clips no permite verificar el umbral de **≥ 50% de hablantes de 30 años o más**. CORdeBA declara mediana de 24 años. | `R2` + `[ACTUALIZACION]` | TSV Common Voice y ficha CORdeBA | **Pendiente** |
| R3 | Medido | 46,4% de las horas son espontáneas (6,9 h de 15,0 h) | `R3` | — | **No** |
| F1 | Estimado + medido | Las tres declaran transcripción humana. 20 de 28 filas de Humyn no cumplen su ficha (ninguna de las 6 en castellano) | `F1` | Fichas | **En parte** |
| F3 | No medido | Doble transcripción de 44 clips (uno por hablante) | `F3` | — | Pendiente |

![Cobertura de la transcripción](figuras/fig2_cobertura_transcripcion.png)

### Separación de hablantes

Fuentes históricas: AMI, ICSI, VoxConverse (inglés) y Humyn LATAM (castellano). Complementarias: CALLHOME Spanish (llamadas sin sesiones independientes identificadas) y Figshare v2 (nueve sesiones de juego de dos participantes). Que la métrica de diarización sea independiente del idioma no implica que su rendimiento sea independiente de idioma, canal o dominio.

| Id | Medido o estimado | Resultado | Celda | Si es estimado, procedencia | Cumple |
|---|---|---|---|---|---|
| V3 | Medido | 700 sesiones y 236 h en fuentes históricas; AMI/ICSI tienen audio para 246/246 reuniones. Figshare agrega **9 sesiones** verificadas (219 tareas), mientras CALLHOME tiene 140 registros sin identificación de sesiones independientes. | `V3` + `[ACTUALIZACION]` | — | Sí |
| C2 | Medido | 100,0% de los turnos con hablante | `C2` | — | Sí |
| K2 | Medido | Históricos: 12 turnos con fin ≤ inicio (AMI 2, Humyn 10). CALLHOME: **2/28.112** intervalos originales con fin ≤ inicio; **159/3.168** segmentos de 15 audios inspeccionados terminan más de 10 ms después del audio (2 registros). Son anomalías distintas, preservadas y no puntuables sin tratamiento. | `K2` + `[ACTUALIZACION]` | — | **No** |
| G2 | Estimado | 0 de 4 fuentes de videollamada | `G2` | Documentación de las fuentes | **No** |
| R4 | Medido | Históricas: 70,4% de las 700 sesiones tienen 3 a 8 hablantes. Figshare: **0/9** sesiones con 3 a 8 (son de dos personas); CALLHOME no permite contar sesiones independientes. | `R4` + `[ACTUALIZACION]` | — | Sí (fuentes históricas) |
| R6 | Medido | 57,8% de las horas son de reuniones reales | `R6` | — | Sí |

![Horas por fuente](figuras/fig1_horas_por_fuente.png)

![Hablantes por sesión](figuras/fig3_hablantes_por_sesion.png)

![Tiempos contra audio](figuras/fig4_tiempos_contra_audio.png)

### Minuta

Fuente: AMI (inglés).

| Id | Medido o estimado | Resultado | Celda | Si es estimado, procedencia | Cumple |
|---|---|---|---|---|---|
| M1 | Medido | 105 reuniones con resumen, decisiones y acciones, en 37 series (142 con alguna minuta; 2.602 ítems, sin 47 marcadores `*NA*`) | `M1` | — | Sí |
| M2 | Medido | 3,5% de las horas con minuta son de reuniones reales (2,6 h de 75,1 h) | `M2` | — | **No** |
| M3 | No medido | El equipo etiqueta una muestra de ítems y se compara contra el juez | `M3` | — | Pendiente |
| C4 | Medido | 90,5% de las 972 decisiones y acciones tienen un fragmento enlazado (22.100 enlaces, 137 reuniones) | `C4` | — | Sí |
| R5 | Medido | 0 de 142 minutas en castellano | `R5` | — | **No**: se traduce (dataset derivado) |

### De punta a punta

| Id | Medido o estimado | Resultado | Celda | Si es estimado, procedencia | Cumple |
|---|---|---|---|---|---|
| V5 | Medido | 0 reuniones en castellano con audio, transcripción, hablantes y minuta | `V5` | — | **No**: reuniones propias |

## 3. Exposición al *leakage*

No hay entrenamiento. Se busca lo que inflaría la evaluación.

| Búsqueda | Qué se busca | Resultado | Celda |
|---|---|---|---|
| La definición | Columnas posteriores al momento de predecir | 65 de 151 columnas son anotación posterior; 13 apuntan al audio. La minuta se evalúa sobre la salida del transcriptor, no sobre la transcripción manual | `L1` |
| El tiempo | Si el modelo ya vio los datos | pyannote entrenó o ajustó con **154 de 171** reuniones de AMI; quedan **91 no vistas** (16 AMI + 75 ICSI). Las minutas de AMI son públicas hace más de 15 años. Whisper no publica sus datos | `L2` |
| Los duplicados | Exactos y casi exactos | OpenSLR 61: 82,8% de los clips lee una oración que lee otro hablante; AMI: 18,7% de ítems de decisión/acción casi idénticos entre series. Common Voice: **0** repeticiones colaborador/oración con identidad conocida; no equivale a comparar formas de onda. | `L3` + `[ACTUALIZACION]` |
| Los grupos | Varias filas de una misma persona | OpenSLR 61: 44 hablantes/5.739 clips; AMI: 37 series/142 minutas; ICSI: un hablante participa en 49 de 75 reuniones. Common Voice: **0** colaboradores identificados compartidos entre `train`, `dev` y `test` de origen; Figshare debe separarse por sesión; CALLHOME no posee grupos verificables. | `L4` + `[ACTUALIZACION]` |
| La generación | Cómo se produjo cada dato | OpenSLR 61: 100% lectura. AMI: 72,5% de las horas y 97,2% de las minutas son de reuniones actuadas. ICSI: 5,2% del habla es lectura de dígitos | `L5` |

**Consecuencias:** separar por hablante (OpenSLR 61 y colaboradores Common Voice), por serie (AMI) y por sesión comprobada (Figshare). CALLHOME no tiene grupos de sesión recuperados: no se presume independencia de sus 140 registros. Las 91 reuniones AMI/ICSI indicadas históricamente como no vistas dependen del sistema/versión efectivamente evaluado; la ausencia en su lista de entrenamiento no acredita ausencia de preentrenamiento. Las minutas AMI siguen siendo únicamente una referencia de evaluación en inglés, con posible exposición previa del modelo.
