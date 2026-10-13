# Datasheet abreviada

**Documento 3 de 4 del [Hito 2](README.md)**

**Equipo:** Luisa, Bruno, Matías, Felipe.

**Muestra:** [`hito-2/muestra/`](muestra/) · **Fecha de revisión:** 2026-10-13

Las mediciones están en el [EDA](2-eda-de-viabilidad.md) y se regeneran desde su [notebook](notebooks/eda_viabilidad.ipynb). Los resultados normalizados y acústicos son derivados locales: no se redistribuyen originales restringidos.

---

## 1. Motivación

**1. ¿Para qué se creó el dataset?**

Respuesta: Ninguno de los datasets utilizados fue creado específicamente para nuestro objetivo: generar automáticamente minutas a partir de grabaciones de reuniones en castellano.

Las fuentes originales fueron desarrolladas con distintos propósitos, principalmente relacionados con el reconocimiento del habla, la diarización de hablantes y el análisis de conversaciones. En nuestro proyecto, se utilizan para evaluar la viabilidad de los distintos módulos del sistema: transcripción, identificación de hablantes y generación de minutas.

| Fuente | Propósito original | Uso en nuestro proyecto |
|---|---|---|
| OpenSLR 61 | Investigación y desarrollo de tecnologías de síntesis de voz en español argentino | Evaluar transcripción en castellano rioplatense |
| CORdeBA | Investigación lingüística del español bonaerense espontáneo | Evaluar transcripción de habla espontánea |
| Humyn LATAM | Desarrollo y evaluación de tecnologías de reconocimiento del habla en español latinoamericano | Evaluar transcripción y diarización en castellano |
| Common Voice | Construcción de un corpus abierto y multilingüe para tecnologías de reconocimiento del habla | Evaluar transcripción en castellano leído y analizar la disponibilidad de información demográfica de los hablantes |
| AMI | Investigación sobre reconocimiento y comprensión automática de reuniones | Evaluar diarización y generación de minutas |
| ICSI | Investigación sobre reconocimiento del habla y análisis de reuniones espontáneas | Evaluar diarización |
| VoxConverse | Desarrollo y evaluación de sistemas de diarización en grabaciones audiovisuales | Referencia adicional para diarización (descartada) |
| CALLHOME | Investigación sobre reconocimiento del habla y análisis de conversaciones telefónicas espontáneas | Evaluar diarización en castellano |
| Figshare v2 | Investigación de la interacción entre dos personas durante actividades lúdicas | Evaluar diarización en castellano |

**2. ¿Quién lo creó, y por encargo de quién?**

Respuesta:

| Fuente | Quién lo creó | Por encargo de quién |
|---|---|---|
| OpenSLR 61 | Equipo de investigación de Google, con grabaciones de voluntarios de Buenos Aires | No sabemos |
| CORdeBA | Universidad Nacional de La Plata (UNLP) | No sabemos |
| Humyn LATAM | Humyn Labs | No sabemos |
| Common Voice | Mozilla Data Collective, con aportes de voluntarios de todo el mundo | Mozilla Foundation (iniciativa propia) |
| AMI | Consorcio de investigación AMI, coordinado por la Universidad de Edimburgo | Unión Europea (Sexto Programa Marco de investigación) |
| ICSI | International Computer Science Institute (ICSI), Berkeley | No sabemos |
| VoxConverse | Investigadores de la Universidad de Oxford | Programa EPSRC Seebibyte y becas de Google |
| CALLHOME | Linguistic Data Consortium (LDC) y Rutgers University | No sabemos |
| Figshare v2 | Autores del estudio SIS | No sabemos |

## 2. Composición

**3. ¿Qué representa cada instancia, y cuántas hay?**

La normalización común complementa la muestra histórica con **16.156 instancias de transcripción** (10.393 Common Voice, 5.739 OpenSLR 61 y 24 CORdeBA); **359 registros de grabación para diarización** (219 Figshare, 140 CALLHOME), que no equivalen a grabaciones o sesiones independientes; **49.492 segmentos** (21.382 Figshare, 28.110 CALLHOME) y tablas auxiliares de hablantes (434 ASR, 374 diarización). Los identificadores de CALLHOME tienen alcance local al registro y **no son personas ni sesiones independientes acreditadas**. Figshare agrupa 219 pares en **nueve sesiones**. A continuación se conserva el inventario histórico de fuentes complementarias.

Respuesta:

| Fuente | Tabla | Módulo | Qué representa cada instancia | Cuántas hay |
|---|---|---|---|---|
| OpenSLR 61 | `slr61/transcripciones.csv` | Transcripción | El texto de una oración leída en español rioplatense | 5.739 |
| OpenSLR 61 | `slr61/manifiesto_audio.csv` | Transcripción | Las características acústicas del mismo clip: duración, frecuencia de muestreo y pico de amplitud | 5.739 |
| CORdeBA | `cordeba/grabaciones.csv` | Transcripción | Los metadatos de una grabación de habla espontánea en español bonaerense | 24 |
| CORdeBA | `cordeba/turnos.parquet` | Transcripción | El texto de un turno espontáneo en español bonaerense: hablante y texto, sin tiempos | 5.187 |
| Humyn LATAM | `humyn/grabaciones.csv` | Transcripción | Los metadatos de una grabación de habla espontánea en castellano | 28 |
| Humyn LATAM | `humyn/turnos.parquet` | Transcripción | El texto y tiempos de un turno espontáneo en castellano: hablante, inicio, fin, texto | 445 |
| AMI | `ami/reuniones.csv` | Hablantes | Los metadatos de una reunión en inglés (mayormente actuada): serie, índice de audio | 171 |
| AMI | `ami/participantes.csv` | Hablantes | El perfil de una persona: código, sexo, edad y lengua nativa | 189 |
| AMI | `ami/turnos.parquet` | Hablantes | Un turno de habla actuada en inglés: hablante, inicio, fin, texto | 93.637 |
| AMI | `ami/extractos_energia.parquet` | Hablantes | La energía de 20 ms de un fragmento de 30 s de audio de reunión en inglés | 24.000 |
| AMI | `ami/minutas.parquet` | Minuta | Un ítem de minuta de reunión en inglés: resumen, decisión, acción o problema | 2.649 |
| AMI | `ami/evidencias.parquet` | Minuta | Un fragmento de transcripción en inglés que respalda un ítem de minuta | 22.100 |
| ICSI | `icsi/reuniones.csv` | Hablantes | Los metadatos de una reunión en inglés espontánea: serie, índice de audio | 75 |
| ICSI | `icsi/hablantes.csv` | Hablantes | El perfil de una persona: código, sexo, edad y lengua nativa | 61 |
| ICSI | `icsi/turnos.parquet` | Hablantes | Un turno de habla espontánea en inglés: hablante, inicio, fin, texto | 129.106 |
| ICSI | `icsi/extractos_energia.parquet` | Hablantes | La energía de 20 ms de un fragmento de 30 s de audio de reunión en inglés | 12.000 |
| VoxConverse | `voxconverse/rttm.parquet` | Hablantes | Un tramo de audio espontáneo en inglés (video de YouTube) en que habla una persona | 27.747 |

**4. ¿Es todo lo que existe o una muestra?**

Respuesta: El conjunto de datos reúne fuentes con distintos niveles de cobertura. Para OpenSLR 61, CORdeBA, Humyn LATAM, AMI, ICSI y VoxConverse se dispone de la totalidad de las distribuciones identificadas. En cambio, Common Voice corresponde a un subconjunto de un corpus multilingüe, del cual se descargaron 10.393 grabaciones en español rioplatense (9.903 de entrenamiento, 266 de validación y 224 de prueba). Por su parte, Figshare v2 corresponde a una distribución pública específica del material UBA Games, que no representa la totalidad del corpus original de CONICET.

Para CALLHOME se obtuvieron cinco archivos Parquet procesados que contienen 140 registros. Sin embargo, no se pudo verificar si estos representan la totalidad de las conversaciones del corpus original ni cuántas sesiones independientes contienen.

A partir de las fuentes obtenidas se construyeron cinco tablas normalizadas para las tareas de transcripción y diarización. Si bien se procesaron las anotaciones y los metadatos disponibles, el análisis acústico se realizó sobre una selección de grabaciones o extractos de audio. En particular, para AMI e ICSI se analizaron 24 extractos, de los cuales se conservaron únicamente las mediciones de energía por cuadro.

Los audios originales no se incluyen en el repositorio y permanecen almacenados localmente, sujetos a las condiciones de uso de cada fuente.

**5. Si es una muestra, ¿de qué, y es representativa?**

Respuesta: Para el análisis acústico se seleccionaron muestras de las grabaciones disponibles en cada fuente. En Common Voice se analizaron 30 clips (10 por cada conjunto de entrenamiento, validación y prueba); en OpenSLR 61, 44 archivos de audio, uno por hablante; en CORdeBA, 8 grabaciones; en Figshare v2, 9 extractos de 30 segundos, uno por sesión; y en CALLHOME, 15 registros, tres por cada archivo Parquet.

Para AMI e ICSI se seleccionaron 24 extractos de audio de 30 segundos, correspondientes a distintas series de reuniones: 16 de AMI (4 ES, 4 IS, 4 TS, 2 EN y 2 IB) y 8 de ICSI (3 Bmr, 3 Bro y 2 Bed). Esta distribución buscó incluir diferentes grupos de reuniones, pero no fue proporcional a la cantidad de horas disponibles en cada uno.

La selección se realizó mediante criterios definidos y reproducibles, utilizando una semilla fija (20261010) cuando correspondía. Sin embargo, no se diseñó como un muestreo probabilístico representativo de las fuentes originales.

Por lo tanto, las muestras permiten realizar una evaluación exploratoria de la calidad y las características acústicas de los datos, pero no pueden considerarse estadísticamente representativas del dominio objetivo de reuniones en castellano. Esta limitación es especialmente relevante porque algunas fuentes contienen grabaciones en otros idiomas o situaciones de habla diferentes de las reuniones que se busca procesar.

**6. ¿Falta información?**

Respuesta: Sí, se identificaron datos faltantes y limitaciones en las anotaciones disponibles, que varían según la fuente.

En Common Voice, el 97,5 % de los 10.393 clips cuenta simultáneamente con información de edad, género y acento. Sin embargo, esta cobertura se calcula por grabación y no por hablante, por lo que no permite determinar la proporción de personas con información demográfica completa.

En Humyn LATAM, las transcripciones cubren el 71,4 % de la duración total del audio. En CORdeBA, las transcripciones no cuentan con marcas temporales que permitan ubicar las intervenciones dentro de las grabaciones y, además, 3 de las 24 transcripciones no separan los hablantes.

En AMI, 29 de las 171 reuniones no cuentan con una minuta asociada. Por su parte, CALLHOME no dispone de identificadores que permitan distinguir de manera independiente las sesiones y tampoco contiene minutas, dado que corresponde a conversaciones telefónicas. En Figshare v2, el repositorio conserva únicamente nueve mezclas cortas para inspección, mientras que los 219 pares de audio completos permanecen en la caché local.

La principal limitación para el objetivo del proyecto es que ninguna de las fuentes dispone de minutas de referencia en castellano. Aunque AMI incluye minutas, estas se encuentran en inglés.

Finalmente, todavía no se pudo verificar la distribución de edades por hablante para evaluar el requisito de que al menos el 50 % de los participantes tenga 30 años o más, ya que la información disponible no permite realizar esa comprobación a nivel de persona.

**7. ¿Hay errores, ruido o duplicados?**

Respuesta: Sí, el análisis exploratorio identificó duplicaciones, inconsistencias temporales y problemas de calidad en algunas fuentes.

En OpenSLR 61, se detectaron 78 clips (1,4 % del total) que repiten la combinación de hablante y oración, aunque esto no implica necesariamente que los archivos de audio sean idénticos.

En las anotaciones temporales se encontraron 12 turnos inválidos (2 de AMI y 10 de Humyn LATAM), cuya duración es nula o negativa. En CALLHOME se identificaron otros 2 intervalos inválidos entre 28.112 registros originales. Además, en 2 de los 15 audios inspeccionados de CALLHOME, las anotaciones exceden la duración real de la grabación en 187,73 y 260,12 segundos, respectivamente.

Respecto de la integridad de los archivos, 105 de los 106 audios seleccionados para la auditoría acústica pudieron decodificarse. El único archivo que presentó problemas fue CORdeBA_0016.wma, previamente identificado como ilegible. En Figshare v2, los 219 pares de audio cumplen con la tolerancia temporal de 10 milisegundos establecida para las diferencias entre canales.

En las minutas de AMI, 47 de los 2.649 ítems contienen el marcador *NA*, en lugar de contenido válido.

Por otra parte, no se encontraron colaboradores identificados compartidos entre los conjuntos de entrenamiento, validación y prueba de Common Voice. Sin embargo, esto no permite descartar posibles solapamientos con los datos de preentrenamiento de modelos externos.

Finalmente, no se realizó una evaluación sistemática de los errores en el contenido de las transcripciones, por lo que todavía no es posible cuantificar su precisión ni determinar la magnitud del ruido en las anotaciones textuales.

**8. ¿Depende de recursos externos, con licencias o costos?**

Respuesta: Sí. Los datos provienen de fuentes externas sujetas a diferentes licencias, permisos y condiciones de uso. Su adquisición no tuvo costos monetarios directos.

OpenSLR 61 utiliza la licencia CC BY-SA 4.0 y CORdeBA CC BY-NC-SA 4.0. Ambas requieren atribución y establecen condiciones de ShareAlike para la distribución de materiales derivados; CORdeBA, además, restringe el uso comercial. Humyn LATAM, AMI, ICSI, VoxConverse y Figshare v2 declaran licencias CC BY 4.0, que requieren atribución.

Common Voice declara CC0, pero su descarga mediante Mozilla Data Collective requiere aceptar condiciones adicionales de acceso y uso. Por este motivo, el archivo original no se redistribuye desde el repositorio. CALLHOME, obtenido mediante una distribución procesada de TalkBank, requiere acceso autorizado y tampoco se redistribuye.

Los archivos originales de audio y los materiales sujetos a restricciones permanecen fuera del repositorio, almacenados localmente o disponibles en los servidores de origen.

Las licencias, condiciones de uso y referencias académicas de cada fuente se documentan en [`muestra/LICENCIAS.md`](muestra/LICENCIAS.md).

**9. Si hay personas, ¿se puede identificar a alguien, directa o indirectamente?**

Respuesta: Sí, existe riesgo de identificación directa o indirecta de los participantes, aunque las fuentes presentan distintos niveles de información personal.

En AMI e ICSI, los participantes están asociados a identificadores codificados, junto con atributos demográficos como sexo, edad y lengua nativa. Si bien estos códigos no revelan directamente su identidad, la combinación de atributos podría facilitar su identificación.

En CORdeBA, Humyn LATAM, AMI e ICSI, las conversaciones espontáneas pueden contener nombres de pila y referencias personales que permitan reconocer a los participantes. En VoxConverse, las grabaciones provienen de videos de YouTube, por lo que algunas personas podrían identificarse a partir del contenido y contexto del video original.

Por su parte, Common Voice utiliza identificadores de colaboradores sin nombres personales, pero las grabaciones conservan la voz de cada participante, que constituye un posible medio de identificación.

En consecuencia, los identificadores codificados no garantizan el anonimato, especialmente cuando se combinan datos demográficos, contenido de las conversaciones y características de la voz. Por este motivo, los datos deben tratarse considerando el riesgo de reidentificación y las condiciones de uso de cada fuente.

**10. ¿Hay datos sensibles?**

Respuesta: Todavía no se realizó una evaluación sistemática del contenido sensible de las grabaciones y transcripciones, por lo que no es posible determinar su alcance en el conjunto de datos.

Como hallazgo puntual, se identificaron opiniones políticas en dos grabaciones argentinas de Humyn LATAM. Además, algunas fuentes presentan riesgos potenciales por la naturaleza de sus contenidos: CORdeBA y CALLHOME incluyen conversaciones privadas; AMI e ICSI, reuniones de trabajo que podrían contener información institucional o profesional confidencial; y VoxConverse, videos públicos que podrían incluir información sensible sobre sus participantes.

Por otra parte, Common Voice y las demás fuentes de audio contienen grabaciones de voz que pueden permitir la identificación de personas, aunque esto no implica por sí solo que se hayan identificado categorías especiales de datos sensibles.

En consecuencia, la presencia y magnitud de información sensible sigue siendo una limitación pendiente de evaluación. Los casos identificados no permiten caracterizar el conjunto completo ni descartar la existencia de otros contenidos sensibles.

## 3. Recolección

**11. ¿Cómo se consiguió cada dato, y en qué período?**

Respuesta: Los datos se obtuvieron mediante descargas realizadas el 10 y 12/10/2026 con [`scripts/descargar_fuentes.py`](scripts/descargar_fuentes.py). La adquisición de Common Voice, CALLHOME y Figshare v2 se verificó el 13/10/2026 mediante tamaños, hashes y manifiestos locales (`fuentes.lock.json`). Los originales se conservan en `.cache/`, sujetos a las condiciones de acceso de cada fuente.

Según las fichas originales, las grabaciones corresponden a 2018–2019 (OpenSLR 61), 2014–2019 (CORdeBA), 2004–2005 (AMI) y 2001–2002 (ICSI). Para Humyn, VoxConverse, Common Voice, CALLHOME y Figshare v2 no se verificó el período de grabación. Las fechas de descarga o publicación no permiten inferir cuándo se registraron las voces.

**12. Si es una muestra, ¿con qué criterio se eligió?**

Respuesta: Los criterios de selección variaron según la fuente. Para AMI e ICSI se eligió al azar con semilla 20261010 y SHA-256 del identificador: un extracto de 30 s por reunión, entre el 20 % y el 80 % de la reunión. Common Voice se estratificó por partición; CALLHOME, por archivo Parquet; en OpenSLR se auditaron 44 FLAC derivados preseleccionados; y en Figshare, nueve mezclas de inspección, no todos los originales. La muestra acústica quedó fijada de forma reproducible. Los archivos [`muestra/normalizado/aptitud/RESULTADOS_B.csv`](muestra/normalizado/aptitud/RESULTADOS_B.csv) e [`INFORME_B.json`](muestra/normalizado/aptitud/INFORME_B.json) documentan la evidencia y procedencia sin incluir audio ni texto.

**13. Si hay personas, ¿sabían que se recolectaban sus datos, y lo consintieron?**

Respuesta: OpenSLR 61: voluntarios. CORdeBA: grabado "con autorización de los participantes" (ficha). Common Voice: no verificado en los archivos descargados. AMI, ICSI y Humyn: no figura en los archivos descargados. VoxConverse: videos públicos de YouTube; no sabemos. CALLHOME y Figshare v2: no verificado.

## 4. Usos

**14. ¿Hay algo en cómo se armó que afecte sus usos?**

Respuesta: Ver EDA, L1 a L5. No sirve para evaluar el producto completo: ninguna reunión tiene castellano, hablantes y minuta a la vez. OpenSLR 61 es lectura, con 44 hablantes para 5.739 clips: se parte por hablante. Common Voice también es habla leída y requiere controlar la identidad de los colaboradores entre splits. CALLHOME tiene 140 registros que no pueden tratarse como sesiones independientes ni todos sus intervalos como referencias válidas. Figshare debe segmentarse por sus nueve sesiones, no por las 219 tareas.

Pyannote entrenó con AMI y VoxConverse: 91 reuniones AMI/ICSI estaban identificadas históricamente como no usadas por una configuración concreta de pyannote, pero debe contrastarse con la versión exacta del modelo evaluado. Las minutas son en inglés y el 97 % de las minutas de AMI corresponde a reuniones actuadas con el mismo guion: se parte por serie. Las observaciones acústicas son parciales; que un extracto se decodifique no garantiza la calidad del audio original completo ni de sus anotaciones.

**15. ¿Para qué tareas no debería usarse?**

Respuesta: No debería utilizarse para identificar personas ni inferir identidades entre registros; para uso comercial mientras incluya CORdeBA; para sacar conclusiones o extrapolar la precisión del producto a reuniones reales de trabajo en castellano; ni para entrenar y evaluar con las mismas personas o series. Tampoco para evaluar CALLHOME sin filtrar las inconsistencias temporales, estimar WER/DER a partir de la auditoría de decodificación o utilizar originales restringidos fuera de las condiciones de acceso y uso aceptadas.
