# Datasheet abreviada

**Documento 3 de 4 del [Hito 2](README.md)**

**Equipo:** Luisa, Bruno, Matías, Felipe.

**Muestra:** [`hito-2/muestra/`](muestra/) · **Fecha:** 2026-10-10

Las mediciones están en el [EDA](2-eda-de-viabilidad.md).

---

## 1. Motivación

**1. ¿Para qué se creó el dataset?**

Respuesta: La muestra, para decidir si la transcripción y la separación de
hablantes se pueden evaluar con datos públicos en inglés. Las fuentes: AMI,
para investigar la comprensión automática de reuniones; ICSI, para el
reconocimiento de voz en reuniones; VoxConverse, para medir separación de
hablantes en videos reales.

**2. ¿Quién lo creó, y por encargo de quién?**

Respuesta: La muestra, el equipo, con [`scripts/armar_muestra.py`](scripts/armar_muestra.py).
AMI: consorcio AMI (la distribuye la Universidad de Edimburgo). ICSI:
International Computer Science Institute, Berkeley. VoxConverse: Universidad
de Oxford. Quién financió cada una: no sabemos.

## 2. Composición

**3. ¿Qué representa cada instancia, y cuántas hay?**

Respuesta:

| Tabla | Cada fila es | Filas |
|---|---|---|
| `ami/reuniones.csv` | Una reunión, con el índice de su audio | 171 |
| `ami/participantes.csv` | Una persona | 189 |
| `ami/turnos.parquet` | Un turno: hablante, inicio, fin, texto | 93.637 |
| `ami/extractos/` | 30 s de audio de una reunión | 16 |
| `icsi/reuniones.csv` | Una reunión, con el índice de su audio | 75 |
| `icsi/hablantes.csv` | Una persona | 61 |
| `icsi/turnos.parquet` | Un turno | 129.106 |
| `icsi/extractos/` | 30 s de audio de una reunión | 8 |
| `voxconverse/rttm.parquet` | Un tramo en que habla una persona | 27.747 |

**4. ¿Es todo lo que existe o una muestra?**

Respuesta: Transcripción, hablantes, tiempos e índice de audio: todo lo que
trae cada fuente. Audio: una muestra, 24 extractos de 30 s (12 minutos de
171,6 horas).

**5. Si es una muestra, ¿de qué, y es representativa?**

Respuesta: Los 24 extractos se eligieron por grupo de reuniones (AMI: 4 ES,
4 IS, 4 TS, 2 EN, 2 IB; ICSI: 3 Bmr, 3 Bro, 2 Bed), con semilla fija. Cubren
todos los sitios de grabación. No son proporcionales a las horas de cada
grupo.

**6. ¿Falta información?**

Respuesta: Ver EDA, C1 a C5. El 11,5% de las palabras de ICSI no tiene
tiempo. 40 de los 190 hablantes de AMI no tienen datos demográficos.
VoxConverse no tiene transcripción.

**7. ¿Hay errores, ruido o duplicados?**

Respuesta: Ver EDA, K1 a K4. Cero duplicados. 2 turnos de duración cero. La
duración de los metadatos de AMI no coincide con el audio en el 20% de las
reuniones. Errores dentro de las transcripciones: no sabemos (EDA, F3).

**8. ¿Depende de recursos externos, con licencias o costos?**

Respuesta: Las tres fuentes son CC BY 4.0 y gratuitas. El audio completo
(26,1 GB) está en servidores de las universidades de Edimburgo y Oxford.
Atribución en [`muestra/LICENCIAS.md`](muestra/LICENCIAS.md).

**9. Si hay personas, ¿se puede identificar a alguien, directa o indirectamente?**

Respuesta: Indirectamente, sí: por la voz (24 extractos), por nombres de
pila dichos en las reuniones y por los datos de cada participante (sexo,
edad, lengua nativa), que están bajo un código.

**10. ¿Hay datos sensibles?**

Respuesta: La voz. No encontramos otros; no se leyeron las transcripciones
completas.

## 3. Recolección

**11. ¿Cómo se consiguió cada dato, y en qué período?**

Respuesta: Descarga del 10/10/2026 con [`scripts/descargar_fuentes.py`](scripts/descargar_fuentes.py).
Grabado en 2004–2005 (AMI) y 2001–2002 (ICSI). VoxConverse: no sabemos.

**12. Si es una muestra, ¿con qué criterio se eligió?**

Respuesta: Extractos al azar con semilla 20261010, por grupo de reuniones;
cada uno empieza entre el 20% y el 80% de la reunión.

**13. Si hay personas, ¿sabían que se recolectaban sus datos, y lo consintieron?**

Respuesta: AMI e ICSI: no figura en los archivos descargados; se publican
con licencia abierta. VoxConverse: videos públicos de YouTube; no sabemos.

## 4. Usos

**14. ¿Hay algo en cómo se armó que afecte sus usos?**

Respuesta: Ver EDA, L1 a L5. pyannote entrenó con AMI y VoxConverse: solo 91
reuniones sirven para evaluarlo. Las mismas personas se repiten entre
reuniones: se parte por serie. El 72,5% de las horas de AMI son reuniones
actuadas. Todo es presencial y de 2001–2005.

**15. ¿Para qué tareas no debería usarse?**

Respuesta: Identificar personas por la voz. Sacar conclusiones sobre
videollamadas o sobre otros idiomas. Entrenar y evaluar con las mismas
reuniones.
