# Datasheet abreviada

**Documento 3 de 4 del [Hito 2](README.md)**

**Equipo:** Luisa, Bruno, Matías, Felipe.

**Muestra:** [`hito-2/muestra/`](muestra/) · **Fecha:** 2026-10-12

Las mediciones están en el [EDA](2-eda-de-viabilidad.md).

---

## 1. Motivación

**1. ¿Para qué se creó el dataset?**

Respuesta: La muestra, para decidir si cada módulo del producto (transcribir,
separar hablantes, escribir la minuta) se puede evaluar con datos públicos.
Las fuentes: OpenSLR 61, para sintetizar voz en castellano de Latinoamérica;
CORdeBA, para estudiar el castellano bonaerense; Humyn LATAM, muestra
comercial para reconocimiento de voz; AMI e ICSI, para investigar reuniones;
VoxConverse, para medir separación de hablantes.

**2. ¿Quién lo creó, y por encargo de quién?**

Respuesta: La muestra, el equipo, con [`scripts/armar_muestra.py`](scripts/armar_muestra.py).
OpenSLR 61: Google. CORdeBA: Universidad Nacional de La Plata. Humyn LATAM:
Humyn Labs. AMI: consorcio AMI (Universidad de Edimburgo). ICSI:
International Computer Science Institute, Berkeley. VoxConverse: Universidad
de Oxford. Quién financió AMI, ICSI y VoxConverse: no sabemos.

## 2. Composición

**3. ¿Qué representa cada instancia, y cuántas hay?**

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

Respuesta: Texto, hablantes, tiempos, minutas e índices de audio: todo lo que
trae cada fuente. Audio: ninguno. De 24 extractos de AMI e ICSI se guarda
solo la energía por cuadro.

**5. Si es una muestra, ¿de qué, y es representativa?**

Respuesta: Los 24 extractos de los que se guarda la energía se eligieron por
grupo de reuniones (AMI: 4 ES, 4 IS, 4 TS, 2 EN, 2 IB; ICSI: 3 Bmr, 3 Bro,
2 Bed); no son proporcionales a las horas.

**6. ¿Falta información?**

Respuesta: Ver EDA, C1, C2, C4 y C5. En Humyn el texto cubre el 71,4% del
audio. CORdeBA no tiene tiempos y 3 de sus 24 transcripciones no separan
hablantes. 29 de las 171 reuniones de AMI no tienen minuta. Ninguna fuente en
castellano trae la edad.

**7. ¿Hay errores, ruido o duplicados?**

Respuesta: Ver EDA, K1 a K4. 78 clips de OpenSLR 61 repiten hablante y
oración. 12 turnos de duración cero. 1 archivo de CORdeBA no es audio. 47
ítems de las minutas son el marcador `*NA*`. Errores dentro de las
transcripciones: no sabemos (EDA, F3).

**8. ¿Depende de recursos externos, con licencias o costos?**

Respuesta: Sin costo. OpenSLR 61: CC BY-SA 4.0. CORdeBA: CC BY-NC-SA 4.0
(no comercial). Humyn, AMI, ICSI y VoxConverse: CC BY 4.0. El audio completo
está en los servidores de cada fuente. Atribución en
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

Respuesta: Descarga del 10 y 12/10/2026 con [`scripts/descargar_fuentes.py`](scripts/descargar_fuentes.py).
Grabado en 2018–2019 (OpenSLR 61, según su ficha), 2014–2019 (CORdeBA, según
su ficha), 2004–2005 (AMI) y 2001–2002 (ICSI). Humyn y VoxConverse: no
sabemos.

**12. Si es una muestra, ¿con qué criterio se eligió?**

Respuesta: Al azar con semilla 20261010: un extracto de 30 s por reunión
elegida en AMI e ICSI, entre el 20% y el 80% de la reunión.

**13. Si hay personas, ¿sabían que se recolectaban sus datos, y lo consintieron?**

Respuesta: OpenSLR 61: voluntarios. CORdeBA: grabado "con autorización de los
participantes" (ficha). AMI, ICSI y Humyn: no figura en los archivos
descargados. VoxConverse: videos públicos de YouTube; no sabemos.

## 4. Usos

**14. ¿Hay algo en cómo se armó que afecte sus usos?**

Respuesta: Ver EDA, L1 a L5. No sirve para evaluar el producto completo:
ninguna reunión tiene castellano, hablantes y minuta a la vez. OpenSLR 61 es
lectura, con 44 hablantes para 5.739 clips: se parte por hablante. pyannote
entrenó con AMI y VoxConverse: solo 91 reuniones sirven para evaluarlo. Las
minutas son en inglés y el 97% son de reuniones actuadas con el mismo guion:
se parte por serie.

**15. ¿Para qué tareas no debería usarse?**

Respuesta: Identificar personas. Uso comercial, mientras incluya
CORdeBA. Sacar conclusiones sobre reuniones reales en castellano. Entrenar y
evaluar con las mismas personas o series.
