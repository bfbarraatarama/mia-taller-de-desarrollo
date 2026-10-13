# Datasheet abreviada

**Documento 3 de 4 del [Hito 2](README.md)**

**Equipo:** Luisa, Bruno, Matías, Felipe.

**Muestra:** [`hito-2/muestra/`](muestra/) · **Fecha de revisión:** 2026-10-13

Las mediciones están en el [EDA](2-eda-de-viabilidad.md) y se regeneran desde su [notebook](notebooks/eda_viabilidad.ipynb). Los resultados normalizados y acústicos son derivados locales: no se redistribuyen originales restringidos.

---

## 1. Motivación

**1. ¿Para qué se creó el dataset?**

Respuesta: La muestra, para decidir si cada módulo del producto (transcribir,
separar hablantes, escribir la minuta) se puede evaluar con datos públicos.
Las fuentes: OpenSLR 61, para sintetizar voz en castellano de Latinoamérica;
CORdeBA, para estudiar el castellano bonaerense; Humyn LATAM, muestra
comercial para reconocimiento de voz; AMI e ICSI, para investigar reuniones;
VoxConverse, para medir separación de hablantes. Common Voice 26 Rioplatense se creó para habla leída de colaboradores; CALLHOME Spanish registra llamadas telefónicas espontáneas y UBA Games Figshare v2 reúne tareas de interacción lúdica. **No** se produjeron como reuniones de trabajo con minuta.

**2. ¿Quién lo creó, y por encargo de quién?**

Respuesta: La muestra, el equipo, con [`scripts/armar_muestra.py`](scripts/armar_muestra.py).
OpenSLR 61: Google. CORdeBA: Universidad Nacional de La Plata. Humyn LATAM:
Humyn Labs. AMI: consorcio AMI (Universidad de Edimburgo). ICSI:
International Computer Science Institute, Berkeley. VoxConverse: Universidad
de Oxford. Common Voice: comunidad Mozilla/Data Collective; CALLHOME: TalkBank (distribución procesada en Hugging Face); Figshare v2: autores de la distribución SIS. Quién financió AMI, ICSI y VoxConverse: no sabemos.

## 2. Composición

**3. ¿Qué representa cada instancia, y cuántas hay?**

La normalización común complementa la muestra histórica con **16.156 instancias de transcripción** (10.393 Common Voice, 5.739 OpenSLR 61 y 24 CORdeBA); **359 registros de grabación para diarización** (219 Figshare, 140 CALLHOME); **49.492 segmentos** (21.382 Figshare, 28.110 CALLHOME) y tablas auxiliares de hablantes (434 ASR, 374 diarización). Los identificadores de CALLHOME tienen alcance local al registro y **no son personas ni sesiones independientes acreditadas**. Figshare agrupa 219 pares en **nueve sesiones**. A continuación se conserva el inventario histórico de fuentes complementarias.

Respuesta:

| Módulo | Tabla | Cada fila es | Filas |
|---|---|---|---|
| Transcripción | `slr61/transcripciones.csv` | Un clip leído, con su texto | 5.739 |
| | `slr61/manifiesto_audio.csv` | Un audio de la fuente: duración, frecuencia, pico | 5.739 |
| | `cordeba/grabaciones.csv` | Una grabación | 24 |
| | `cordeba/turnos.parquet` | Un turno: hablante y texto, sin tiempos | 5.187 |
| | `humyn/grabaciones.csv` | Una grabación | 28 |
| | `humyn/turnos.parquet` | Un turno en castellano: hablante, inicio, fin, texto | 445 |
| Hablantes | `ami/reuniones.csv`, `icsi/reuniones.csv` | Una reunión, con el índice de su audio | 171 y 75 |
| | `ami/participantes.csv`, `icsi/hablantes.csv` | Una persona | 189 y 61 |
| | `ami/turnos.parquet`, `icsi/turnos.parquet` | Un turno: hablante, inicio, fin, texto | 93.637 y 129.106 |
| | `ami/extractos_energia.parquet`, `icsi/extractos_energia.parquet` | La energía de 20 ms de audio de un extracto de 30 s | 24.000 y 12.000 |
| | `voxconverse/rttm.parquet` | Un tramo en que habla una persona | 27.747 |
| Minuta | `ami/minutas.parquet` | Un ítem de la minuta de referencia: resumen, decisión, acción o problema | 2.649 |
| | `ami/evidencias.parquet` | Un fragmento de la transcripción que respalda un ítem | 22.100 |

**4. ¿Es todo lo que existe o una muestra?**

**Actualización comprobable:** La distribución de Figshare v2 es una porción específica del material UBA Games, no el corpus CONICET completo. CALLHOME consta de cinco Parquet procesados; su cardinalidad de 140 registros no prueba completitud de llamadas ni sesiones independientes. Common Voice incluye el TAR y sus 10.393 MP3/TSV declarados, no otros idiomas o variantes.

Respuesta: Se incluyen las anotaciones e índices disponibles de las fuentes históricas y las cinco tablas comunes. No se redistribuyen audios originales; permanecen en la caché local bajo las condiciones de cada fuente. De 24 extractos AMI/ICSI se conserva sólo la energía por cuadro.

**5. Si es una muestra, ¿de qué, y es representativa?**

**Actualización comprobable:** La auditoría acústica selecciona 10 MP3 por split de Common Voice (30), 44 FLAC preseleccionados de OpenSLR, ocho grabaciones CORdeBA —incluida la marcada ilegible—, nueve mezclas de 30 segundos de Figshare y tres registros por cada uno de cinco Parquet CALLHOME (15). Se selecciona determinísticamente, pero no es una muestra probabilística representativa del dominio de reuniones.

Respuesta: Los 24 extractos de los que se guarda la energía se eligieron por
grupo de reuniones (AMI: 4 ES, 4 IS, 4 TS, 2 EN, 2 IB; ICSI: 3 Bmr, 3 Bro,
2 Bed); no son proporcionales a las horas.

**6. ¿Falta información?**

**Actualización comprobable:** Common Voice dispone simultáneamente de edad, género y acento en el **97,5%** de los clips (faltan 139 edades, 261 géneros y ningún acento); son metadatos por clip, no proporciones de hablantes. CORdeBA carece de tiempos alineados. CALLHOME no acredita grupos de sesión ni contiene minutas. Figshare sólo dispone en el repositorio de nueve mezclas cortas de inspección; sus WAV originales completos quedan en caché local. Ninguna fuente aporta la referencia de minuta en castellano del producto completo.

Respuesta: Ver EDA, C1, C2, C4 y C5. En Humyn el texto cubre el 71,4% del
audio. CORdeBA no tiene tiempos y 3 de sus 24 transcripciones no separan
hablantes. 29 de las 171 reuniones de AMI no tienen minuta. En las fuentes históricas no constaba edad por hablante; Common Voice incorpora una columna opcional, cuya completitud quedó medida por clip. No se verificó todavía R2 por persona.

**7. ¿Hay errores, ruido o duplicados?**

**Actualización comprobable:** La normalización conservó dos anomalías temporales CALLHOME (28.112 intervalos originales, 28.110 válidos estructuralmente); en dos de 15 audios muestreados sus anotaciones exceden la duración por 187,73 y 260,12 s. Los 219 pares Figshare respetan la tolerancia de 10 ms (213 requieren aceptarla). De 106 archivos acústicos seleccionados, 105 se decodificaron; el único no decodificable fue CORdeBA_0016.wma. La superposición textual entre voces no implica identidad de audio; no se encontraron colaboradores identificados compartidos entre los splits originales de Common Voice (0), sin que ello acredite independencia frente a preentrenamientos externos.

Respuesta: Ver EDA, K1 a K4. 78 clips de OpenSLR 61 repiten hablante y
oración. 12 turnos de duración cero. 1 archivo de CORdeBA no es audio. 47
ítems de las minutas son el marcador `*NA*`. Errores dentro de las
transcripciones: no sabemos (EDA, F3).

**8. ¿Depende de recursos externos, con licencias o costos?**

**Actualización comprobable:** Common Voice se obtuvo tras aceptar condiciones de Mozilla Data Collective; las referencias del proyecto declaran CC0, pero el acceso/redistribución debe regirse además por los términos aceptados. CALLHOME requiere permiso de acceso a TalkBank/Hugging Face y no se redistribuye. Figshare v2 declara CC BY 4.0. CORdeBA prohíbe uso comercial (CC BY-NC-SA 4.0). Los originales restringidos y el audio no se incluyen en la entrega.

Respuesta: Sin costo monetario directo en esta adquisición, pero con permisos y condiciones de uso. OpenSLR 61: CC BY-SA 4.0. CORdeBA: CC BY-NC-SA 4.0
(no comercial). Humyn, AMI, ICSI y VoxConverse: CC BY 4.0. Los originales completos están en la caché local o en el servidor de cada fuente según las condiciones de acceso. Atribución en
[`muestra/LICENCIAS.md`](muestra/LICENCIAS.md).

**9. Si hay personas, ¿se puede identificar a alguien, directa o indirectamente?**

Respuesta: Indirectamente, sí: por nombres de pila
dichos en las conversaciones y por los datos de cada participante de AMI e
ICSI (sexo, edad, lengua nativa), que están bajo un código.

**10. ¿Hay datos sensibles?**

Respuesta: Opiniones políticas en las dos grabaciones argentinas de
Humyn. Conversaciones privadas en CORdeBA; no se leyeron completas.

## 3. Recolección

**11. ¿Cómo se consiguió cada dato, y en qué período?**

**Actualización comprobable:** La adquisición de Common Voice, CALLHOME y Figshare se verificó el 13/10/2026 con tamaño, hash y manifiestos locales (`fuentes.lock.json`). La fecha de descarga o publicación **no demuestra** el año de captación de cada voz. Los originales quedan en `.cache/`, con acceso reproducible según licencias y credenciales propias.

Respuesta: Descarga del 10 y 12/10/2026 con [`scripts/descargar_fuentes.py`](scripts/descargar_fuentes.py).
Grabado en 2018–2019 (OpenSLR 61, según su ficha), 2014–2019 (CORdeBA, según
su ficha), 2004–2005 (AMI) y 2001–2002 (ICSI). Humyn y VoxConverse: no
sabemos.

**12. Si es una muestra, ¿con qué criterio se eligió?**

**Actualización comprobable:** La muestra acústica quedó fijada por semilla 20261010 y SHA-256 del identificador; Common Voice estratifica por partición y CALLHOME por Parquet. En OpenSLR se auditan 44 FLAC derivados preseleccionados y en Figshare nueve mezclas, no todos los originales. `muestra/normalizado/aptitud/RESULTADOS_B.csv` e `INFORME_B.json` documentan evidencia y procedencia sin contener audio ni texto.

Respuesta: Al azar con semilla 20261010: un extracto de 30 s por reunión
elegida en AMI e ICSI, entre el 20% y el 80% de la reunión.

**13. Si hay personas, ¿sabían que se recolectaban sus datos, y lo consintieron?**

Respuesta: OpenSLR 61: voluntarios. CORdeBA: grabado "con autorización de los
participantes" (ficha). AMI, ICSI y Humyn: no figura en los archivos
descargados. VoxConverse: videos públicos de YouTube; no sabemos.

## 4. Usos

**14. ¿Hay algo en cómo se armó que afecte sus usos?**

**Actualización comprobable:** Los 140 registros CALLHOME no pueden tratarse como sesiones autónomas ni todos los intervalos normalizados como referencias puntuables. Figshare requiere segmentar por sus nueve sesiones y no por las 219 tareas. Common Voice exige controlar identidad de colaborador entre splits y es habla leída. Las observaciones acústicas son parciales: un FLAC o mezcla decodificable no valida el original completo ni la calidad de una anotación.

Respuesta: Ver EDA, L1 a L5. No sirve para evaluar el producto completo:
ninguna reunión tiene castellano, hablantes y minuta a la vez. OpenSLR 61 es
lectura, con 44 hablantes para 5.739 clips: se parte por hablante. pyannote
entrenó con AMI y VoxConverse: 91 reuniones AMI/ICSI estaban identificadas históricamente como no usadas por una configuración concreta; esto debe contrastarse con la versión exacta del modelo evaluado. Las
minutas son en inglés y el 97% son de reuniones actuadas con el mismo guion:
se parte por serie.

**15. ¿Para qué tareas no debería usarse?**

**Actualización comprobable:** Tampoco para evaluar sin filtrado temporal CALLHOME, para estimar WER/DER a partir de la auditoría de decodificación, ni para extrapolar la precisión del producto a reuniones de trabajo en castellano. No se permite inferir identidades de personas entre registros ni utilizar originales restringidos fuera de las condiciones aceptadas.

Respuesta: Identificar personas. Uso comercial, mientras incluya
CORdeBA. Sacar conclusiones sobre reuniones reales en castellano. Entrenar y
evaluar con las mismas personas o series.
