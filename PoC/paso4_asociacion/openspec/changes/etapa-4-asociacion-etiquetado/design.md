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

Precisiones de la implementación: la palabra anterior es la anterior en todo `asr.json`, aunque esté en otro segmento de Whisper; el largo de un turno es el de la unión de los turnos de esa etiqueta que se tocan o se superponen.

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

Precisiones de la implementación: si hay candidatos, el tramo solo más largo siempre está entre ellos, así que los respaldos solo se usan cuando no hay ninguno; un respaldo de más de 15 s también se recorta a sus 15 s centrales; el punto medio de una palabra cuenta si cae en `[start, end)`.

### D7. Integración con el pipeline

A acordar con Bruno: el orquestador `procesar.py` es suyo (plan 4.1). Entornos: interfaz y Etapa 4 en Python 3.14 (`.venv` de la raíz); Etapas 2 y 3 en 3.12 con PyTorch; Etapa 5 en 3.12 con Ollama.

**Pausa para etiquetar**

| Alternativa | Descripción | Resultado |
|---|---|---|
| A | Un proceso del orquestador que espera la confirmación de la interfaz | Descartada: el proceso conserva el contexto CUDA de PyTorch durante el etiquetado (no medido; suele ser de cientos de MB, con 6 GB y Qwen en 4,7 GB); si la interfaz se cierra, queda colgado |
| B | Dos corridas; el orquestador asocia y escribe un archivo intermedio para las fichas | Descartada: agrega un contrato nuevo |
| **C** | **Dos corridas; la interfaz corre la Etapa 4: `procesar.py --hasta transcribir` → `asociar()` + fichas + `escribir()` → `procesar.py --desde minuta`** | **Elegida** |

Motivo: usa solo archivos que ya tienen contrato, el proceso con GPU termina antes de las fichas, se puede volver a etiquetar sin repetir las Etapas 2 y 3, y la latencia de 2.3 es la suma de las dos corridas (la segunda con `--t-pedido` al confirmar). Sin interfaz, el orquestador corre la Etapa 4 por CLI, sin nombres. Pedido a Bruno: las opciones `--hasta transcribir` y `--desde minuta` (nombres a acordar).

**API**

| Función | Entrada | Salida |
|---|---|---|
| `asociar(carpeta, audio=None, diarizacion=None, asr=None)` | Carpeta de la reunión y rutas opcionales | Intervenciones, fichas con candidatos de fragmento, meta parcial. No escribe nada |
| `escribir(asociacion, nombres, salida=None)` | Resultado de `asociar`, `{etiqueta: nombre o None}` o `None` (sin etiquetado), fragmento en pantalla por etiqueta | `transcription.json`, `transcription.meta.json` y, si hubo etiquetado, `speakers.json` |

**Rutas**

| Alternativa | Descripción | Resultado |
|---|---|---|
| A | Siempre rutas explícitas | Descartada: el orquestador repite 4 rutas con nombres fijos |
| B | Carpeta de la reunión con nombres fijos | Descartada: obliga a copiar o renombrar los archivos de S26 y de la Etapa 3 para evaluar |
| **C** | **Carpeta por defecto (`audio.wav`, `diarization.json`, `asr.json`) y rutas explícitas opcionales; salida en la carpeta o en `--salida`** | **Elegida** |

### D8. Interfaz de las fichas

Verificado en la máquina de referencia: el `.venv` de la interfaz no tiene QtMultimedia (`pyside6-essentials` no lo incluye); sounddevice tiene salida de audio.

| Decisión | Alternativas | Elegida | Motivo |
|---|---|---|---|
| Dónde | A diálogo modal · B dentro del panel · C ventana no modal | **A: `QDialog` modal con `QScrollArea`** | Bloquea grabar y procesar mientras se etiqueta (3.1.5) sin código extra; el cierre es el lugar de la pregunta de 3.3. B no tiene lugar para 8 fichas (2.1.3); C deja grabar a mitad del etiquetado |
| Reproducción | A sounddevice · B QtMultimedia · C reproductor del sistema | **A: `soundfile.read(start=, stop=)` + `sd.play`; ▶/■ alterna; una reproducción a la vez** | Sin dependencias nuevas, como prevé el pipeline; lee solo el fragmento. B exige `pyside6-addons`; C no se puede detener |
| Ayudas | A mínimo · B + autocompletado, contador y aviso · C + todas las intervenciones | **B** | El autocompletado evita los errores de tipeo que la unificación (2.4) no cubre; el contador avisa cuando «Otro fragmento» empieza a repetir (D6); el aviso de superposición lo exige D6. C alarga las fichas en el caso de 8 hablantes |

La lógica de las fichas (orden, candidatos, nombres, unificación, opciones de cierre) vive en un modelo sin Qt; el diálogo solo la muestra.

### D9. Pruebas

Verificado en la máquina de referencia: no están Figshare (S26) ni los `asr.json` de la Etapa 3 (`data/`); sí Humyn, 4 grabaciones propias de la Etapa 1 y la GPU. `pytest` no está en el `.venv` de la interfaz.

| Decisión | Alternativas | Elegida | Motivo |
|---|---|---|---|
| Niveles | A solo unitarias · B tres niveles · C B + error de atribución por palabra contra Figshare | **B: 1 unitarias (un test por escenario) · 2 integración con las Etapas 2 y 3 reales en la GPU sobre grabaciones propias, lectura por la Etapa 5 y proporción de marcas y empates · 3 contrato sobre la muestra congelada de 2.3** | El nivel 2 cubre además las tareas 7.3, 7.4 y 7.5 de la Etapa 2 y mide lo pendiente de D2 y D5. El nivel 3 depende de la muestra congelada (semana 7). C no entra en la semana y 2.3 no le pone umbral |
| Interfaz | A lista manual · B `pytest-qt` · C modelo sin Qt + lista manual | **C** | Los escenarios de etiquetado son lógica; lo visual y el audio se comprueban escuchando, como en la cobertura de 2.3 |
| Orden | A de abajo hacia arriba · B esqueleto de punta a punta primero · C interfaz primero | **B** | Meta de la semana 8: *baseline* de punta a punta; destraba a la Etapa 5 y la tarea 7.5 de la Etapa 2 |

`pytest` va en `requirements-dev.txt` del módulo. Cada test lleva el nombre de su escenario.

### D10. Ejemplo ideal

Entradas perfectas y consistentes entre sí para desarrollar y probar sin las Etapas 2 y 3 («para probar sola» del documento del pipeline). Verificado: espeak-ng 1.51 con `es-419` y variantes distinguibles (`+f3`, `+m3`); genera 22 050 Hz, mono, PCM16.

| Alternativa | Descripción | Resultado |
|---|---|---|
| A | Un tono por hablante con NumPy y JSON a mano | Descartada: sin voces para la lista manual ni contenido para la Etapa 5 |
| B | Guion grabado por el equipo y JSON con tiempos marcados de oído | Descartada: el marcado agrega errores, requiere consentimiento y deja voces reales en el repo |
| **C** | **Guion sintetizado con espeak-ng por un script; turnos y palabras exactos por construcción** | **Elegida** |

Motivo: tiempos sin error de marcado, así que el happy path exige el 100 % de atribución correcta; voces que se escuchan en las fichas; reproducible y sin datos personales (se versionan el script y el guion, no el WAV); da a la Etapa 5 un `transcription.json` con 2 temas y 1 acción.

| Detalle | Valor |
|---|---|
| Guion | ≈ 60 a 75 s; Ana (`es-419+f3`) abre y presenta el presupuesto del trimestre en una intervención de más de 15 s; Carlos (`es-419+m3`) discute la fecha de la demo y toma la acción «Yo mando el informe el viernes»; Sofía (`es-419+f1`) cierra y confirma la decisión. Nombres ficticios |
| Audio | Intervenciones concatenadas sin superposición, con 0,6 s de silencio entre ellas; remuestreo a 16 kHz con `scipy.signal.resample_poly` |
| `diarization.json` | Un turno por intervención, con los tiempos de la concatenación y etiquetas `SPEAKER_00` a `SPEAKER_02` |
| `asr.json` | Un segmento por intervención; tiempos de palabra repartidos en proporción a sus letras dentro de la intervención |
| `referencia.json` | Hablante y nombre esperados por palabra, para comparar |
| Fuera del ejemplo | Solapamientos, huecos y empates: se prueban con JSON chicos a mano (tareas 3.x) y con datos reales (nivel 2) |
