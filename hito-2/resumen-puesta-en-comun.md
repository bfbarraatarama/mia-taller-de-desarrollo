# Hito 2 en una página

**Equipo:** Luisa, Bruno, Matías, Felipe · **Alcance:** producto en castellano, evaluado por módulo

## 1. Qué hicimos y cómo

El objetivo del hito fue responder una pregunta: ¿existen datos públicos que permitan evaluar un sistema que transcribe reuniones, separa hablantes y escribe la minuta, en castellano?

**Paso 1 — Buscar y obtener las fuentes** · [1-mapa-de-fuentes.md](1-mapa-de-fuentes.md)
Ninguna fuente tiene todo. Elegimos una por módulo: audio rioplatense con transcripción (OpenSLR 61, CORdeBA, Humyn), reuniones con hablantes anotados (AMI, ICSI, VoxConverse) y reuniones con minuta de referencia (AMI).

**Paso 2 — Fijar los niveles antes de medir** · [niveles-a-priori.md](niveles-a-priori.md)
25 umbrales mínimos, asignados a un módulo cada uno: volumen, completitud, corrección, vigencia, representatividad y confiabilidad.

**Paso 3 — Armar la muestra** · [`scripts/armar_muestra.py`](scripts/armar_muestra.py)
Un script descarga las fuentes y construye una muestra estructurada: tablas con clips, reuniones, hablantes, turnos, minutas y sus enlaces de evidencia. Está en [`muestra/`](muestra/), sin audio.

**Paso 4 — Correr el EDA** · [notebooks/eda_viabilidad.ipynb](notebooks/eda_viabilidad.ipynb)
El notebook mide los 25 niveles, una sección por módulo, y busca exposición a *leakage*. Resultados en [`resultados_eda.csv`](resultados_eda.csv) y [`resultados_leakage.csv`](resultados_leakage.csv); gráficos en [`figuras/`](figuras/).

**Paso 5 — Documentar los datos** · [3-datasheet.md](3-datasheet.md)

**Paso 6 — Decidir** · [4-veredicto.md](4-veredicto.md)
Ajustar el alcance: evaluar por módulo y grabar reuniones propias para el producto completo.

---

## 2. Lo esencial

25 niveles: 10 se cumplen, 9 no, 3 en parte, 3 pendientes.

| Módulo | Número |
|---|---|
| Transcripción | 15,0 h de audio rioplatense, 44 hablantes. Solo 46,4% es espontáneo, y casi todo sin tiempos |
| Separación de hablantes | 700 sesiones, 236 h. pyannote ya vio 154 de las 171 de AMI: quedan 91 para evaluar |
| Minuta | 105 reuniones con minuta completa; 90,5% de los ítems con evidencia. **Todas en inglés**; 97% actuadas |
| De punta a punta | **0 reuniones en castellano con todo** |

**Veredicto: ajustar el alcance.**

1. **Obtención:** un conjunto de evaluación por módulo, partido por hablante o por serie.
2. **Limpieza:** fuera duplicados, turnos inválidos y marcadores vacíos; CORdeBA se alinea; AMI se traduce al castellano (dataset derivado).
3. **Estructura:** por módulo: audio + texto; audio + turnos; turnos + ítems con citas.

## 3. La decisión que tomamos, y qué descartamos

- Castellano, evaluado por módulo: no hace falta un dataset que tenga todo.
- Minuta sobre AMI traducido, con sus enlaces de evidencia.
- 10 reuniones propias en castellano para el producto completo.
- Descartado: Common Voice espontáneo (0,08 h validadas); VoxConverse como evaluación principal.

## 4. Nuestro mayor riesgo

No completar las 10 reuniones propias. Sin ellas, el producto queda evaluado solo por partes, y la minuta, solo sobre texto traducido.

## 5. Qué necesitamos del docente

- Si la minuta evaluada sobre AMI traducido vale como evidencia, declarada como dato sintético.
- Si 10 reuniones propias alcanzan para la evaluación de punta a punta.
