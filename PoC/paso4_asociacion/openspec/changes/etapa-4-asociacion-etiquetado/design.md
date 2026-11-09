# Design

## Contexto

Entradas: `audio.wav` (Etapa 1), `diarization.json` (Etapa 2, PR #8) y `asr.json` (Etapa 3, PR #9). Salida: `transcription.json`, que lee `src/minutas/entrada.py` (Etapa 5, PR #6). Los umbrales se fijan antes de medir sobre palabras reales.

Medición sobre las 25 diarizaciones de S26 publicadas por la Etapa 2 (predicción de pyannote, no referencia; 2 hablantes, dominio de juego). Script: `stats_s26.py` y `tramos_solos.py`, a versionar en `evaluacion/`.

| Medida | Valor |
|---|---|
| Turnos · hablantes por archivo | 678 · 1 a 2 |
| Habla superpuesta | 152,4 de 1.513,0 s (10,1 %) |
| Turnos contenidos enteros en un turno de otro hablante | 157 (23 %) |
| Turnos de menos de 0,5 s | 149 (22 %) |
| Huecos sin hablante · mediana · menores de 0,5 s | 391 · 0,54 s · 180 (46 %) |
| Hablantes sin ningún tramo en que hablen solos | 16 de 49 (`SPEAKER_01` en 16 de 25 archivos) |

No medido: cuántas palabras de Whisper caen en tramos superpuestos, en huecos o en empates (no hay `asr.json` de S26).

## Decisiones

### D1. Regla de asignación palabra → hablante

| Alternativa | Descripción | Resultado |
|---|---|---|
| A | Turno que contiene el punto medio de la palabra | Descartada: usa un solo instante; sensible a bordes corridos |
| **B** | **Hablante con más segundos de turno dentro de `[word.start, word.end]`** | **Elegida** |
| C | Todo el segmento de Whisper al hablante que más lo cubre | Descartada: pierde cambios de hablante dentro del segmento; el documento del pipeline la excluye |

Motivo: es la regla del documento del pipeline y usa toda la duración de la palabra. Un segmento de `asr.json` con `words: []` se trata como una sola palabra con los tiempos y el texto del segmento.

### D2. Empate: la palabra cae entera en turnos de dos o más hablantes

| Alternativa | Descripción | Resultado |
|---|---|---|
| A | El turno más corto | Descartada: acierta solo si Whisper transcribió la interrupción |
| **B** | **El hablante de la palabra anterior si está entre los empatados; si no, el del turno más largo; si persiste, la etiqueta menor** | **Elegida** |
| C | `speaker: null` | Descartada: deja sin hablante hasta el 10,1 % del habla |

Motivo: en las interrupciones cortas (23 % de los turnos), Whisper tiende a transcribir la voz dominante; la B no parte la intervención del que tiene la palabra. No medido: tasa de acierto, a medir con `asr.json` reales. La intervención queda marcada con `overlap` (D5).

### D3. Palabra sin turno que la cubra

| Alternativa | Descripción | Resultado |
|---|---|---|
| A | `speaker: null` siempre | Descartada: el 46 % de los huecos mide menos de 0,5 s |
| B | Turno más cercano, sin límite | Descartada: presenta como segura una atribución que no lo es (2.2) |
| **C** | **Turno más cercano si la distancia es ≤ 0,25 s; si no, `null`** | **Elegida** |

Motivo: 0,25 s es el margen por borde del DER con tolerancia NIST que usa la Etapa 2; un solo criterio de borde corrido en el equipo. Empate de distancia: misma regla que D2.

### D4. Armado de intervenciones

| Alternativa | Descripción | Resultado |
|---|---|---|
| A | Cortar solo por cambio de hablante | Descartada: un monólogo de 3 min queda como una cita de 3 min |
| B | Cortar por cambio de hablante o por pausa ≥ X s | Descartada: agrega un umbral sin respaldo |
| **C** | **Cortar por cambio de hablante y en cada límite de segmento de Whisper** | **Elegida** |

Motivo: la Etapa 5 cita el `start` de cada intervención para comprobarla en el audio (2.2); los segmentos de Whisper traen frases con puntuación. El texto es la concatenación de las palabras separadas por un espacio; `start` y `end` son los de su primera y última palabra. `speaker: null` (D3) también corta la intervención.

### D5. Marcas de confianza

Booleanos, no puntaje (2.2, punto 2). Umbrales del documento del pipeline: 0,2 s y 30 %. Se calculan sobre `[start, end]` de la intervención, en milisegundos enteros para que los valores límite no dependan del redondeo en coma flotante.

**`overlap`**

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **≥ 0,2 s acumulados con 2 o más hablantes activos** | **Elegida** |
| B | Cualquier superposición | Descartada: marca los roces de borde y el 23 % de turnos contenidos; la marca deja de distinguir |
| C | ≥ 10 % de la duración | Descartada: no marca un «no» de 0,3 s en una intervención de 12 s |

Motivo: «hay otra voz encima» pide un umbral absoluto; 0,2 s ya está en el documento aprobado.

**`ambiguous`**

| Alternativa | Descripción | Resultado |
|---|---|---|
| A | `speaker: null`, o un segundo hablante cubre ≥ 30 % | Descartada: texto de Whisper sin habla en la diarización, a menos de 0,25 s de un turno, sale atribuido sin marca |
| **B** | **A, o los turnos de su propio hablante cubren menos del 50 %** | **Elegida** |
| C | ≥ 30 % de las palabras decididas por D2 o D3 | Descartada: D2 ya está cubierto por `overlap`; agrega un umbral |

Motivo: Whisper puede producir texto en tramos de ruido o silencio (comportamiento conocido, no medido en este proyecto); ese texto no tiene respaldo en la diarización y podría generar una acción inventada con responsable (2.3). «Ningún turno la cubre» se generaliza a «su hablante la cubre poco». Cobertura: duración de la unión de los turnos de esa etiqueta dentro de `[start, end]`, dividida por `end − start`; el segundo hablante es la otra etiqueta con más cobertura.

No medido: proporción de intervenciones marcadas. Se mide en la Parte 9 sin cambiar los umbrales después de ver los resultados.

### D6. Fragmento por hablante

Regla pedida por Matías (09/11/2026): tramo al azar de duración al menos media, de 15 s como máximo, recortando el que se pase. Reemplaza «el tramo más largo» del documento del pipeline.

Tramo solo: intervalo máximo en que esa etiqueta es la única activa en `diarization.json` (turnos contiguos de la misma etiqueta se unen). Medición en S26: media de los tramos solos por hablante con mediana de 1,99 s (0,92 a 4,30 s), 0 de 33 con media ≥ 5 s, 27 de 49 hablantes con algún tramo ≥ 5 s, 0 tramos > 15 s y 16 de 49 sin ningún tramo solo.

| Alternativa | Descripción | Resultado |
|---|---|---|
| A | Al azar entre tramos con media ≤ d ≤ 15 s; recortar si solo hay > 15 s | Descartada: en S26 da 2 a 4 s, fuera de los 5 a 15 s de 2.2; 16 hablantes sin fragmento |
| **B** | **Al azar entre tramos con d ≥ máx(media, 5 s); los de más de 15 s se recortan a sus 15 s centrales. Respaldo 1: el tramo solo más largo. Respaldo 2: el turno más largo aunque se superponga, con aviso en la ficha** | **Elegida** |
| C | Unir varios tramos cortos hasta 5 a 15 s | Descartada: `speakers.json` guarda un solo intervalo |

Motivo: conserva el azar, la representatividad, el tope y el recorte, respeta los 5 a 15 s de 2.2 sin versionar la definición de la PoC y cubre a los 16 hablantes sin tramo solo. Los 15 s centrales evitan los bordes, donde la diarización es menos confiable (D3).

| Detalle | Valor |
|---|---|
| Media | De los tramos solos de ese hablante |
| Semilla | Primeros 8 bytes del SHA-256 de `diarization.json`; se registra en `transcription.meta.json` |
| «Otro fragmento» | Siguiente candidato de una permutación con esa semilla, sin repetir; agotados los candidatos, siguen los respaldos y vuelve a empezar |
| Texto del fragmento | Palabras de `asr.json` cuyo punto medio cae dentro del fragmento |
