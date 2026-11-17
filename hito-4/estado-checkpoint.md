# Hito 4 · Checkpoint

Estado de la PoC contra la spec de la [definición de la PoC](../hito-3/definicion-de-la-poc.md) (§2.3), al 17/11/2026, sobre `main` en `f606d8b`. Cada número enlaza al archivo del repo que lo produce.

---

## 1. Demo en vivo

| | |
|---|---|
| Entrada | Reunión de prueba: OSM LatAm 2022-07-30, fragmento de 339 s en castellano ([muestra del #14](../evaluacion/integral/resultados/baseline/muestra/)) |
| Recorrido | Grabar desde la interfaz → procesar → nombrar hablantes en las fichas → transcripción con nombres y marcas temporales → minuta |
| Comando | `pw-jack .venv/bin/python -m src.interfaz` |
| Duración esperada | 4 a 5 min de procesamiento en la RTX 3050 (máximo medido: 261 s) |

---

## 2. Estado contra la spec

| Criterio (§2.3) | Umbral | Resultado | Estado | Evidencia |
|---|---|---|---|---|
| Calidad de la respuesta | 2/2 temas, 1/1 acción y 0 inventadas, en las 2 modalidades | Un archivo: 1/2 temas, 0/1 acción, 2 inventadas. Varios archivos: 1/2 temas, 1/1 acción, 1 inventada | **No cumple** | [`calidad.md`](../evaluacion/integral/resultados/baseline/calidad.md) |
| Funcionamiento modular | 4/4 módulos al 100 % | 4/4: diarización 74/74, transcripción 79/79, asociación 74/74, minutas 77/77 | **Cumple** | [`contratos.json`](../evaluacion/modular/resultados/contratos.json) |
| Latencia (p100) | 5/5 corridas en 1800 s o menos | 5/5; máximo 261,0 s para 339 s de audio | **Cumple** | [`reporte.md`](../evaluacion/integral/resultados/baseline/reporte.md) |
| Cobertura de los casos borde | 7/7 marcados por un tercero | 7/7 con comprobación automática; recorrido del tercero sin hacer | **Parcial** | [`escenarios.json`](../evaluacion/escenarios/resultados/escenarios.json), [`PROTOCOLO.md`](../evaluacion/escenarios/PROTOCOLO.md); happy path y 2.1.1 en el PR #25 |
| Recuperación ante interrupciones | 1/1: 5 s perdidos o menos, procesable, listado como interrumpido | 0,25 s perdidos de 130 s; procesado completo; listado como interrumpido. Aviso al reiniciar sin verificar | **Cumple en lo medido** | [`recuperacion.json`](../evaluacion/escenarios/resultados/recuperacion.json) |
| Ventaja sobre el *baseline* | No aplica (3.1.1) | — | — | — |

Lectura: 2 criterios cumplen, 1 cumple en lo medido, 1 está parcial y 1 no cumple.

### Recortes y stubs

| | Estado |
|---|---|
| Stubs en `src` | Ninguno |
| Recortes respecto de la spec | Ninguno. Fuera de alcance desde el Hito 3 (§1.3): personalización terminológica, evaluación automática de minutas, optimización de rendimiento, hardware de bajos recursos y comparación de modelos |
| Comprobaciones solo visuales | Fichas por hablante (happy path, 2.1.2, 2.1.3), avance de etapas y aviso de recuperación al reiniciar: en el protocolo del tercero |

---

## 3. Resultados de la evaluación

### 3.1 Calidad de la minuta (reunión de prueba)

Evaluador: Bruno F. Barra Atarama, autor de las notas de referencia y ajeno a las corridas.

| Ítem | Un archivo (corrida 01) | Varios archivos (corrida 02) |
|---|---|---|
| Tema 1: foro y organización de mapatones | Parcial: falta la organización de mapatones | Parcial: falta la organización de mapatones |
| Tema 2: materiales de capacitación | Sí | Sí |
| Acción: Rafael abre un tema sobre mapatones en el foro | No: la reemplaza un concurso de logos atribuido a «Jorge» | Sí |
| Acciones inventadas | 2: propuestas o descripciones registradas como compromisos | 1: una pregunta registrada como compromiso |
| Cumple | No | No |

Observación: en la corrida 01, el operador nombró «jorge» en las fichas al hablante al que en el audio llaman «Rafael». El nombre del responsable viene de esa ficha; el contenido de la acción, no.

### 3.2 Por módulo (muestra congelada, SHA-256 `68b31711…`)

Sin umbral (§2.3): sin un *baseline* con que comparar, se informan como referencia.

| Módulo | Métrica | Valor | Evidencia |
|---|---|---|---|
| Transcripción | WER / CER total | 26,9 % / 20,1 % (Figshare 27,0 %; OpenSLR 9,1 %; Common Voice 0 %) | [`metricas_stt.json`](../evaluacion/modular/resultados/metricas_stt.json) |
| Diarización | DER estricto / con tolerancia NIST / JER | 21,3 % / 10,7 % / 41,0 % | [`metricas_diarizacion.json`](../evaluacion/modular/resultados/metricas_diarizacion.json) |
| Asociación | Palabras con el hablante correcto | 87,7 % (86,7 % fuera de la superposición) | [`metricas_asociacion.json`](../evaluacion/modular/resultados/metricas_asociacion.json) |
| Minutas (AMI) | Ítems de la minuta de referencia recuperados | 22/55 marcados (acciones 3/8, decisiones 7/15); 1 sin marcar | [`planilla_minutas.json`](../evaluacion/modular/resultados/planilla_minutas.json) |

### 3.3 Casos borde

| Escenario | Comprobación automática | Pendiente del tercero |
|---|---|---|
| Happy path | Graba en el directorio elegido y procesa completo (3 hablantes, 215 s) | Avance de etapas y fichas |
| 2.1.1 Terminología | Conserva el audio y transcribe sin adaptación; «Discourse» sale «discurso» | Confirmar la lista de términos |
| 2.1.2 Voces y superposición | Sí (15,2 s superpuestos conservados) | Mismo nombre en dos etiquetas |
| 2.1.3 Seis o más hablantes | Sí (6 etiquetas en ICSI Bro015) | Una ficha por hablante |
| 2.1.4 Ruido | Sí | — |
| 2.1.5 Más largo que el contexto | Sí (30 archivos, una transcripción, minuta en 27 bloques) | — |
| Error del sistema | Sí (0,25 s perdidos) | Aviso al reiniciar |

### 3.4 Decisión según §1.2

| Condición de §1.2 | Estado medido |
|---|---|
| GO: todos los criterios de §2.3 | No: falla calidad |
| Ajustar: falla alguno, pero la minuta recupera 1 tema y 1 acción sin inventar ninguna | No alcanza: las 2 modalidades inventan acciones |
| NO GO: agotados los planes B de §1.4, no recupera ninguna acción o inventa alguna | Plan B del riesgo 2 sin ejecutar |

Decisión del equipo: **[a completar por el equipo]**.

---

## 4. Plan de cierre

| Ítem | Tipo | Cambia lo que ve el jurado | Responsable | Fecha |
|---|---|---|---|---|
| Plan B del riesgo 2: minuta desde la transcripción corregida a mano, para ubicar el módulo que falla | Mejora | Sí: calidad | [a completar] | [a completar] |
| Según el resultado: cambiar el modelo de diarización o de ASR, o ajustar el prompt para no registrar propuestas como compromisos | Mejora | Sí: calidad | [a completar] | [a completar] |
| Volver a medir la calidad en las 2 modalidades, con las mismas notas de referencia | Evaluación | Sí | [a completar] | [a completar] |
| Recorrido del tercero con `PROTOCOLO.md` | Evaluación | Sí: casos borde y recuperación | [a completar] | [a completar] |
| Integrar los PR #22 (reproducibilidad) y #25 (happy path y 2.1.1) | Cierre | No | [a completar] | [a completar] |
| Modelos (Whisper `medium`, pyannote `community-1`, `qwen2.5:7b`), muestra congelada y reunión de prueba | Se congela | — | — | — |
| Tag `alcance-congelado` (fin de la semana 10) | Entrega | — | [a completar] | [a completar] |
