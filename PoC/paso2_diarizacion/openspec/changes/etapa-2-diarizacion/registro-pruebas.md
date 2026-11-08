# Registro de pruebas — Etapa 2 (diarización)

Pruebas manuales de la Etapa 2 sobre grabaciones reales de la Etapa 1, hechas antes de los tests automáticos del grupo 5 (tareas 5.2 a 5.5). Las grabaciones no están versionadas: se identifican por nombre y SHA-256.

| Prueba | Grabación | Escenario | Estado para la tarea 5.2 |
|---|---|---|---|
| 1 | `2026_11_08_08_47_27.wav` | dos personas en la misma habitación, sin turnos registrados | no corresponde a 5.2 |
| 2 | `2026_11_08_09_07_52.wav` | dos personas en la misma habitación, con turnos controlados | no corresponde a 5.2 |
| 3 | `2026_11_08_09_21_37.wav` | **auriculares con cable**: voz local por el micrófono y voz remota (video) por el sistema | **escenario "auriculares" completado** |
| 4 | `2026_11_08_09_35_54.wav` | **parlantes** de la notebook, sin auriculares | **ejecutado y documentado, con incidencias de captura de la Etapa 1** |
| 5 | `2026_11_08_11_41_26.wav` | **cierre forzado** del proceso de la interfaz durante la captura | **ejecutado y documentado**; reveló un defecto de normalización, corregido en la tarea 2.4 |

Los tres escenarios de la tarea 5.2 están grabados, documentados y verificados. **La tarea 5.2 está completada**, con la excepción de una sola voz en la prueba 5 y la salvedad sobre el consentimiento del video. Ver "Estado de la tarea 5.2" al final. Las tareas 5.3 (test automático de nivel 2, `tests/test_integracion_cpu.py`) y 5.4 (pruebas sintéticas, sección "Tarea 5.4") también están completadas. La 5.5 se completó como verificación automática básica (sección "Tarea 5.5").

## Entorno común

| Elemento | Valor |
|---|---|
| Fecha | 08/11/2026 |
| Máquina | Notebook de desarrollo, Windows 11, sin GPU |
| Etapa 1 | `interfaz.py` en modo Manual, con el `.venv` de la raíz (Python 3.12.10) y lanzado con `-X utf8`. Micrófono **#9 Micrófono (Realtek(R) Audio), WASAPI**; sistema **#13 Mezcla estéreo (Realtek HD Audio Stereo input), WDM-KS** |
| Etapa 2 | `diarizar.py AUDIO --device auto`, **sin `--num-speakers`**. `pyannote/speaker-diarization-community-1`, `pyannote.audio 4.0.7`, `torch 2.8.0+cpu`; dispositivo usado: `cpu` |
| Contrato | `contrato.py diarization.json AUDIO --meta diarization.meta.json`: el validador del contrato y del par JSON/meta |
| Originales | El SHA-256 del WAV y del reporte `.json` de la Etapa 1 se calcula antes y después de diarizar |

## Condición de las pruebas 1 y 2

En las dos, las dos personas estaban en la misma habitación, así que **las dos voces entraron por el micrófono**. La Mezcla estéreo quedó en silencio (alrededor de −93 dBFS) porque no sonó nada por la salida Realtek.

Por eso la Etapa 1 marca **FALLA** en "ambas fuentes registran señal", y pasan "sin pérdidas", "sin desincronización" y "salida procesable". La comprobación del tono no se ejecutó, porque la opción estaba desactivada.

Las pruebas 1 y 2 **no** corresponden a los escenarios de la tarea 5.2. Las pruebas 3, 4 y 5 sí: son los escenarios con auriculares, con parlantes y con cierre forzado.

---

## Prueba 1 — `2026_11_08_08_47_27.wav`: superposición, resultado no confirmado

| Campo | Valor |
|---|---|
| SHA-256 del WAV | `3fe5eeac564950131c3e16d2f9c9ee95839e7331470c7029eb8b06e6fde25e61` |
| Duración | 45,08 s (16 kHz, mono, PCM16) |
| Etapa 1 | `estado: "completa"`; mic −42,2 dBFS, sistema −93,3 dBFS |
| Contenido | Dos personas en la misma habitación, **sin secuencia de turnos registrada** |
| Etapa 2 | `run_id 20261108T085239-cd2312`; código 0; **112,4 s** en CPU |
| Contrato | 0 violaciones (JSON y par JSON/meta); 0 segmentos corregidos y 0 descartados |
| Originales | SHA-256 del WAV y del reporte sin cambios |

**Resultado:** 2 hablantes y 18 segmentos.

| Hablante | Segmentos | Habla | Observación |
|---|---|---|---|
| SPEAKER_00 | 14 | 38,32 s | casi todo el audio |
| SPEAKER_01 | 4 | 3,56 s | **los 4 segmentos caen por completo dentro de segmentos de SPEAKER_00** (22,49–23,23; 32,13–33,34; 42,78–43,45; 44,02–44,95 s) |

- Habla superpuesta entre hablantes: 3,56 s, que es todo el tiempo de SPEAKER_01. El modelo nunca detectó a SPEAKER_01 hablando solo.
- **No confirmado.** No hay una referencia de turnos para saber si:
  - (a) la segunda persona habló poco y siempre encima de la primera; o
  - (b) el modelo **fusionó a las dos personas en SPEAKER_00** y las separó solo donde se superponían. Esto sería el caso 2.1.2, voces similares.
- La distribución de F0 estimada desde el WAV (175–265 Hz, sin dos grupos separados) es compatible con (b), pero no la prueba.
- No se usa como evidencia de calidad: solo sirve como evidencia de que el contrato y el flujo funcionan.

---

## Prueba 2 — `2026_11_08_09_07_52.wav`: turnos controlados, resultado correcto

| Campo | Valor |
|---|---|
| SHA-256 del WAV | `1aa973d93e09041515aa4197d2eecbf3774b3ca49686ec472c977c57816dbfe2` |
| Duración | 45,16 s (16 kHz, mono, PCM16) |
| Etapa 1 | `estado: "completa"`; mic −40,0 dBFS, sistema −93,5 dBFS |
| Secuencia esperada | 0–15 s, persona A · 15–30 s, persona B · 30–45 s, persona A. La tomaron las participantes a mano |
| Etapa 2 | `run_id 20261108T091029-17dd5b`; código 0; **68,1 s** en CPU |
| Contrato | **0 violaciones** (JSON y par JSON/meta); 0 segmentos corregidos y 0 descartados |
| Originales | SHA-256 del WAV y del reporte sin cambios |

**Resultado:** **2 hablantes detectados automáticamente** y 11 segmentos.

| Intervalo esperado | Persona | Segmentos | Hablante asignado | Habla detectada |
|---|---|---|---|---|
| 0–15 s | A | 1,212 → 15,202 s (3 segmentos) | **SPEAKER_01** | 13,48 s |
| 15–30 s | B | 16,012 → 30,710 s (4 segmentos) | **SPEAKER_00** | 13,37 s |
| 30–45 s | A | 31,739 → 45,053 s (4 segmentos) | **SPEAKER_01** | 12,05 s |

- **Reidentificación:** la persona A recibió la misma etiqueta en el primer y el tercer intervalo.
- **Sin confusiones** de hablante dentro de los intervalos y **sin superposiciones** (0,00 s).
- **Desviaciones en los bordes de los turnos:** +0,20 s en el de 15 s y **+0,71 s** en el de 30 s. Equivalen a 0,91 s sobre 38,9 s de habla, unos 2,3 %, si los bordes esperados fueran exactos. Como la secuencia se tomó a mano, no se puede separar el error del modelo del error de la referencia.

---

## Prueba 3 — `2026_11_08_09_21_37.wav`: auriculares con cable (escenario de la tarea 5.2)

| Campo | Valor |
|---|---|
| SHA-256 del WAV | `43f189ec246fe18535df5de4be7e1c79bdaab11f4e73269352445d239cf3a98e` |
| Duración | 45,20 s (16 kHz, mono, PCM16) |
| Escenario | Auriculares con cable en el jack Realtek. Persona A habla por el micrófono; persona B es un video de YouTube que suena por los auriculares y entra por la Mezcla estéreo |
| Secuencia esperada | 0–15 s, A (micrófono) · 15–30 s, B (video, sistema) · 30–45 s, A (micrófono). La tomó la participante a mano |
| Intento previo descartado | `2026_11_08_09_17_12.wav`: el mismo escenario, pero con el volumen del sistema bajo. La Mezcla estéreo quedó en −60,8 dBFS (FALLA por 0,8 dB) y la voz del video unos 10 dB por debajo de la de A. Se repitió con más volumen y no se diarizó |
| Etapa 1 | `estado: "completa"`; **las 4 comprobaciones disponibles en OK** (la del tono no se ejecutó) |
| Etapa 2 | `run_id 20261108T092450-3e2fc2`; código 0; **106,8 s** en CPU |
| Contrato | **0 violaciones** (JSON y par JSON/meta); 0 segmentos corregidos y 0 descartados |
| Originales | SHA-256 del WAV y del reporte sin cambios |

**Etapa 1: las dos fuentes registraron audio.**

| Fuente | RMS | Pico |
|---|---|---|
| Micrófono #9 | −40,4 dBFS | −18,0 dBFS |
| Mezcla estéreo #13 | −32,8 dBFS | −10,6 dBFS |

| Prueba de la Etapa 1 | Resultado |
|---|---|
| Ambas fuentes registran señal | ✅ (umbral −60 dBFS) |
| Sin pérdidas | ✅ 0 overflows; faltante 0,068 / −0,012 s (tolerancia 0,095 s) |
| Sin desincronización | ✅ deriva de 0,080 s |
| Salida procesable | ✅ mono, 16 kHz, PCM 16, sin saturación |

Niveles de la mezcla por intervalo:
- 0–15 s: −37,9 dBFS;
- 15–30 s: −28,4 dBFS, con la voz del video unos 9–10 dB por encima de la de A;
- 30–45 s: −36,3 dBFS. El pico de este intervalo (−12,8 dBFS) supera el máximo del micrófono, lo que indica **posible audio del video después del segundo 30**.

**Etapa 2:** **2 hablantes detectados automáticamente** y **13 segmentos**.

| Intervalo esperado | Persona | Hablante asignado | Segmentos principales | Habla detectada |
|---|---|---|---|---|
| 0–15 s | A (mic) | **SPEAKER_01** | 0,588–5,515 y 5,920–15,927 s | 14,93 s |
| 15–30 s | B (video) | **SPEAKER_00** | 16,012–19,184 y 19,673–29,039 s | 12,54 s |
| 30–45 s | A (mic) | **SPEAKER_01** | 29,039–36,802; 37,021–41,965; 42,218–45,070 s | 15,56 s |

- **Persona A → SPEAKER_01 y persona B → SPEAKER_00.**
- **Reidentificación correcta de la persona A** en el primer y el tercer intervalo.
- **Desviación máxima respecto de los turnos previstos: 0,96 s.** El cambio B → A quedó en 29,039 s, antes del segundo 30. El cambio A → B quedó en ≈ 15,93–16,01 s. No se asignó ningún segmento a B después de 29,039 s: el posible resto del video después del segundo 30 no aparece como B.
- **Superposición detectada: 0,41 s.**
  - B dentro del turno de A: 1,330–1,448 s (0,118 s), un falso positivo.
  - A dentro del turno de B: 16,028–16,315 s (0,287 s).
- **Cuatro microsegmentos de 17 a 34 ms** en el cambio de turno de 15 s (15,927–16,012 s), que alternan SPEAKER_00 y SPEAKER_01. Son válidos para el contrato (`start < end`). La Etapa 4 asigna cada palabra al hablante que más se le superpone, así que se espera que casi no afecten.
- Tiempo atribuido a otro hablante, tomando como exactos los bordes de 15 y 30 s: ≈ 2,3 s sobre 43,5 s de habla (≈ 5,4 %). Como la secuencia se tomó a mano, no se separa del error de la referencia.

---

## Prueba 4 — `2026_11_08_09_35_54.wav`: parlantes (escenario de la tarea 5.2)

| Campo | Valor |
|---|---|
| SHA-256 del WAV | `735a6a8ee6446697cca6b86cbf56e168b6dfdd3f0a5ea08fbfcd90d2e99b91a3` |
| Duración | 45,08 s (16 kHz, mono, PCM16) |
| Escenario | Parlantes de la notebook, sin auriculares. Persona A habla por el micrófono; persona B es un video de YouTube que suena por los parlantes y entra por la Mezcla estéreo |
| Secuencia esperada | 0–15 s, A (micrófono) · 15–30 s, B (video por parlantes) · 30–45 s, A (micrófono). La tomó la participante a mano |
| Etapa 1 | `estado: "completa"`; **2 comprobaciones en OK y 2 en FALLA** (ver observaciones). La del tono no se ejecutó |
| Etapa 2 | `run_id 20261108T093912-51f62b`; código 0; **78,1 s** en CPU |
| Contrato | **0 violaciones** (JSON y par JSON/meta); 0 segmentos corregidos y 0 descartados |
| Originales | SHA-256 del WAV y del reporte sin cambios |

**Etapa 1: niveles y comprobaciones.**

| Fuente | RMS | Pico |
|---|---|---|
| Micrófono #9 | −37,2 dBFS | −16,5 dBFS |
| Mezcla estéreo #13 | −45,7 dBFS | −24,6 dBFS |

| Prueba de la Etapa 1 | Resultado |
|---|---|
| Ambas fuentes registran señal | ✅ (umbral −60 dBFS) |
| Sin pérdidas | ❌ **FALLA**: al micrófono le faltan **0,124 s** (tolerancia 0,095 s), con 0 overflows; al sistema, −0,017 s |
| Sin desincronización | ❌ **FALLA**: deriva de **0,141 s** entre micrófono y sistema |
| Salida procesable | ✅ mono, 16 kHz, PCM 16, sin saturación |

El WAV cumple igual la entrada de la Etapa 2: cabecera válida, lectura completa, 721 280 muestras decodificadas con TorchCodec, iguales a las de la cabecera, y `ffmpeg -v error` sin errores.

Niveles de la mezcla por intervalo: 0–15 s, −35,1 dBFS · 15–30 s, −40,2 dBFS (la voz B unos 4–5 dB por debajo de la de A) · 30–45 s, −36,0 dBFS.

**Observaciones de la Etapa 1 (captura, no diarización).**
- Las dos fallas son de la **captura**. No se atribuyen a la Etapa 2 ni a pyannote.
- **Pérdida de 0,124 s:** el micrófono entregó unos 124 ms menos de audio de lo que indica el reloj, sin overflows. Apunta al flujo de captura del driver o a la carga del sistema, no a bloques descartados.
- **Deriva de 0,141 s:** al final de la grabación, las dos fuentes quedaron desfasadas unos 141 ms. Con auriculares (prueba 3) los mismos valores fueron 0,068 s y 0,080 s, dentro de la tolerancia pero cerca del límite.
- **Causa no determinada.** Una hipótesis no verificada es que el procesamiento del micrófono Realtek ("SST") trabaje más cuando suena algo por los parlantes. Conviene comunicarlo a quien sea responsable de la Etapa 1 y ver si se repite.

**Eco: no se detectaron indicios claros.**
- La autocorrelación de la mezcla entre 20 y 200 ms en el intervalo 15–30 s fue **0,07**. Con auriculares fue 0,06: prácticamente lo mismo, sin el pico que dejaría una voz duplicada.
- En 15–30 s, la mezcla quedó solo **+0,7 dB** por encima del nivel estimado de la Mezcla estéreo sola. El micrófono aportó muy poco mientras sonaba el video.
- Esto coincide con las pruebas de 10 s, en las que el micrófono tampoco captó el pitido de los parlantes. Lo más probable es que el micrófono Realtek cancele el eco. Es un resultado de esta máquina: no confirma ni descarta el problema de eco medido en Fedora para la Etapa 1.

**Etapa 2:** **2 hablantes detectados automáticamente** y **9 segmentos**.

| Intervalo esperado | Persona | Hablante asignado | Segmentos | Habla detectada |
|---|---|---|---|---|
| 0–15 s | A (mic) | **SPEAKER_00** | 0,470 → 17,092 s (4 segmentos) | 15,0 s dentro del intervalo |
| 15–30 s | B (parlantes) | **SPEAKER_01** | 18,290 → 30,406 s (2 segmentos) | 11,52 s |
| 30–45 s | A (mic) | **SPEAKER_00** | 31,199 → 44,851 s (3 segmentos) | 12,79 s |

- **Persona A → SPEAKER_00 y persona B → SPEAKER_01.** En la prueba 3 fue al revés: el número de cada etiqueta lo asigna pyannote.
- **Reidentificación correcta de la persona A.**
- **Sin superposiciones (0,00 s) y sin microsegmentos.** El segmento más corto dura 1,64 s.
- **Desviación máxima respecto de los turnos previstos: 2,09 s.** Está en el cambio de turno de 15 s: A se extiende hasta 17,092 s, sigue un hueco de 1,2 s y B empieza en 18,290 s. En el cambio de 30 s, la desviación es de +0,41 s.
- La causa del desvío de 2,09 s queda **sin determinar**: puede ser un error del modelo, que A siguiera hablando o que el video tardara en empezar. La deriva de captura de 0,141 s es mucho menor y no lo explica.
- Tiempo atribuido a otro hablante, tomando como exactos los bordes: ≈ 2,5 s sobre 39,6 s de habla (≈ 6,3 %).

---

## Prueba 5 — `2026_11_08_11_41_26.wav`: cierre forzado (escenario de la tarea 5.2)

| Campo | Valor |
|---|---|
| SHA-256 del WAV | `de8769ce96d78ca7b855001c936de8091a2cca2c08e12d5bdb02886984251bee` |
| Duración | **32,500 s** (520 000 cuadros; 16 kHz, mono, PCM16) |
| Escenario | Grabación con la interfaz, cortada **a la fuerza** durante la captura. Se usó `Stop-Process -Id 2800 -Force`, que equivale a `TerminateProcess`, sobre el intérprete Python que ejecutaba `interfaz.py`. **No hubo cierre controlado**: no pasó por el Stop, ni por `closeEvent`, ni por el reporte final |
| Proceso | Antes de cerrarlo se verificó su línea de comandos y su padre (el lanzador del venv, PID 11348, que terminó solo). No se cerró ningún otro proceso: los de VS Code (PID 24012 y 9288) siguieron vivos |
| Cierre | 11:41:58.806. La grabación había empezado a las 11:41:26 |
| Etapa 2 | Corrida inicial `run_id 20261108T114340-152f9a`, con la regla original (ver defecto). **Corrida corregida** `run_id 20261108T120142-d600c6`; código 0; 74,6 s en CPU |
| Contrato | **0 violaciones** (JSON y par JSON/meta) |
| Originales | SHA-256 del WAV y del reporte sin cambios, en las dos corridas |

**Etapa 1: grabación interrumpida.**
- El JSON quedó con **`estado: "grabando (si queda así, la grabación se interrumpió)"`**. Es el reporte inicial, de 383 bytes, con archivo, inicio, modo y dispositivos, sin comprobaciones finales, como corresponde a una interrupción.
- El **WAV es válido**:
  - cabecera de 16 kHz, mono y PCM16;
  - `wave.readframes` lee todos los bytes que declara la cabecera (1 040 000);
  - TorchCodec decodifica 520 000 muestras, iguales a la cabecera;
  - `ffmpeg -v error ... -f null -` no da errores.
- **Pérdida estimada: ≈ 0,3 s.** Pasaron 32,806 s desde el inicio hasta el cierre, y el WAV dura 32,500 s. Como el JSON guarda el inicio truncado al segundo, la pérdida real está entre 0,3 y 1,3 s, dentro del límite de **≤ 5 s** de la definición de la PoC.
- La duración, de 32,5 s, está dentro del rango de 30 a 60 s del test de nivel 2.

**Etapa 2: resultado con la regla corregida.**
- La Etapa 2 **aceptó el WAV** aunque el reporte de la Etapa 1 quedó en "grabando": solo valida el WAV.
- **1 hablante (SPEAKER_00) y 8 segmentos**, sin superposiciones. **Habla total: 27,56 s.**
- **Último segmento: 26,592–32,500 s**: llega hasta el final del archivo, donde se cortó la grabación.
- Meta: `segmentos_corregidos: 1`, `segmentos_descartados: 0`, `exceso_fin_max_s: 0.0997` y `tolerancia_fin_s: 0.05` (campo heredado).

| # | Inicio (s) | Fin (s) | Duración (s) |
|---|---|---|---|
| 1 | 0,368 | 2,309 | 1,941 |
| 2 | 2,410 | 3,288 | 0,878 |
| 3 | 4,030 | 8,907 | 4,877 |
| 4 | 9,363 | 14,476 | 5,113 |
| 5 | 14,864 | 19,049 | 4,185 |
| 6 | 19,268 | 21,395 | 2,127 |
| 7 | 22,255 | 24,787 | 2,532 |
| 8 | 26,592 | 32,500 | 5,908 |

**Defecto detectado y corregido (tarea 2.4).**
- La **primera corrida** devolvió 7 segmentos y 21,65 s de habla, con 1 segmento descartado.
- pyannote había devuelto el último tramo como **26,5922–32,5997 s**: 6,0 s de voz real que terminaban 0,0997 s después del final del archivo, por la resolución de sus ventanas.
- La regla original descartaba todo exceso mayor a 0,05 s, y **eliminó ese tramo entero**. Afecta a toda grabación que termina mientras alguien habla, que es justo el caso de una interrupción.
- Se corrigió la spec ("Normalización de segmentos"), el design §4, `segmentos.py`, `diarizar.py`, los tests (con la regresión de este caso) y el README, en la **tarea 2.4**. La regla nueva recorta a los límites del WAV todo segmento con alguna parte dentro del audio, y solo descarta lo que queda fuera del audio o vacío.
- La **segunda corrida** conserva los 8 segmentos, y 92 tests pasan.
- Las pruebas 1 a 4 tenían `segmentos_descartados: 0`, así que la corrección no cambia sus resultados.

**Una sola voz, a propósito:** la grabación se hizo deliberadamente con una sola persona, y el modelo detectó **1 hablante**, como corresponde. El equipo aceptó la excepción al criterio "con 2 voces" de la tarea 5.2, porque el objetivo de esta prueba era la integridad y el procesamiento del WAV después de un cierre inesperado.

## Estado de la tarea 5.2 (revisión del 08/11/2026)

| Criterio de la tarea 5.2 | Estado | Evidencia o faltante |
|---|---|---|
| Grabar con la interfaz (`interfaz.py`) | ✅ | Las pruebas 3, 4 y 5 se grabaron con `interfaz.py` en modo Manual |
| Tres grabaciones de 30 a 60 s | ✅ | 45,20 s, 45,08 s y 32,50 s |
| Escenarios: auriculares, parlantes y cierre forzado | ✅ | Pruebas 3, 4 y 5 |
| Cada WAV con su `.json`: los dos primeros en `"completa"` y el tercero en `"grabando"` | ✅ | Comprobado en los tres |
| `git status` no las muestra | ✅ | `PoC/paso1_captura/grabaciones/` está ignorada; `git check-ignore` lo confirma |
| **Con 2 voces** | ✅ **con una excepción aceptada** | Las pruebas 3 y 4 tienen 2 voces: la persona A y la voz de un video. La **prueba 5 se hizo deliberadamente con una sola voz**, y el equipo aceptó la excepción porque su objetivo era validar la integridad y el procesamiento del WAV después de un cierre inesperado, no la separación de hablantes. El modelo detectó 1 hablante, como corresponde |
| **Con consentimiento de quienes hablan** | ✅ **con una salvedad documentada** | Las grabaciones con dos personas presentes (pruebas 1 y 2) **contaron con el consentimiento de ambas**. En las pruebas 3 y 4, la voz B es un **video público de YouTube**: el equipo acepta su uso en el **contexto académico local**, en grabaciones que no se versionan ni se distribuyen. Queda explícito que **no se verificó el consentimiento individual de ese hablante** |
| **Apuntar `DIARIZACION_AUDIOS_CPU`** | ✅ | Ver el detalle abajo |

**Grabaciones del nivel 2 y `DIARIZACION_AUDIOS_CPU` (decisión del 08/11/2026).**
- La variable apunta a **`PoC/paso1_captura/grabaciones/nivel2/`**, y no a `grabaciones/`. Esa carpeta tiene también la grabación de 15,2 s hecha con Stop (`11_35_20`), que haría fallar el rango de 30 a 60 s del nivel 2, y otras que no son escenarios de la 5.2.
- En `nivel2/` hay **copias** de las tres grabaciones de la 5.2 con sus JSON de la Etapa 1: `09_21_37` (auriculares), `09_35_54` (parlantes) y `11_41_26` (cierre forzado). Su SHA-256 es idéntico al de los originales, que **no se movieron ni se borraron**: siguen en `grabaciones/`, con sus 14 archivos.
- **Mecanismo:** `tests/conftest.py` (fixture `audios_cpu`) lee la variable de entorno; el proyecto no la toma del `.env`, que solo se usa para el token. Se define **en la sesión** que corre las pruebas, sin escribirla de forma permanente en Windows:

  ```powershell
  $env:DIARIZACION_AUDIOS_CPU = (Resolve-Path PoC/paso1_captura/grabaciones/nivel2).Path
  & PoC/paso2_diarizacion/.venv/Scripts/python.exe -m pytest PoC/paso2_diarizacion -m slow -rs
  ```

**Verificaciones de la tarea 5.2 sobre `nivel2/`.**

| Verificación | Resultado |
|---|---|
| Cantidad y estados | **3 WAV**, cada uno con su `.json`: **2 en `"completa"`** (`09_21_37` y `09_35_54`) y **1 en `"grabando"`** (`11_41_26`) |
| Bloque A del nivel 2, por WAV | Los tres dan OK: cabecera de 16 kHz, mono y PCM16; duración de 45,20, 45,08 y 32,50 s, dentro de 30–60 s; lectura completa con `wave`; TorchCodec con las mismas muestras que la cabecera; `ffmpeg -v error` sin errores; y "salida procesable" en OK en las dos completas |
| `git status` | No las muestra: `.gitignore:69` (`PoC/paso1_captura/grabaciones/`) cubre también `nivel2/` |
| `pytest -m slow -rs` (entorno del nivel 2) | **2 de 2 pasan.** `test_entorno_nivel2_cpu` ya no se saltea: hay token, WAV y FFmpeg |
| Nivel 1 | 92 pasan |

**La tarea 5.2 queda completada**, con la excepción de una sola voz en la prueba 5 y la salvedad sobre el consentimiento del video. En ese momento seguían pendientes las tareas 5.3, 5.4 y 5.5. Después se completaron la 5.3 (6 de 6 tests del nivel 2 sobre `nivel2/`) y la 5.4 (sección "Tarea 5.4").

---

## Tarea 5.4 — Pruebas sintéticas de nivel 1

**Objetivo.** Probar la lógica del **bloque A** del nivel 2 (el contrato de la Etapa 1 visto desde la Etapa 2, design.md §10.1) **sin el modelo y en cualquier máquina**, con WAV y reportes sintéticos armados en `tmp_path`. Así, los casos que el test real de la 5.3 no puede reproducir a voluntad (reporte faltante, WAV truncado, estados inválidos) quedan cubiertos en cada corrida del nivel 1.

**Implementación.**
- `PoC/paso2_diarizacion/tests/test_integracion_sintetica.py` llama a **`integracion.verificar_bloque_a`**, la misma función que usa el test de integración real de la 5.3, sin duplicar lógica.
- Usa `torchcodec=False` y `ffmpeg=False`. La decodificación con TorchCodec y FFmpeg queda cubierta por el nivel 2.
- Los WAV se escriben con `escribir_wav` de `conftest.py`, que solo usa `wave`. Los reportes imitan la forma de los de `captura.py`.
- El nombre del archivo hace que `pytest -k integracion` lo seleccione. Los tests `slow` del nivel 2 siguen deseleccionados sin `-m`.

| N.º | Caso | Resultado esperado | Resultado obtenido |
|---|---|---|---|
| 1 | WAV válido de 31 s y JSON con `estado: "completa"` y "salida procesable" en OK | Aceptar | ✅ Aceptado: `interrumpida=False`, 31,0 s, 496 000 cuadros |
| 2 | WAV válido de 32,5 s y JSON en `"grabando (si queda así, la grabación se interrumpió)"` | Aceptar | ✅ Aceptado: `interrumpida=True`, 32,5 s, 520 000 cuadros |
| 3 | WAV válido sin su JSON | Rechazar por reporte faltante | ✅ Rechazado: *"falta el reporte de la Etapa 1 (…json); la grabación no salió de la interfaz"* |
| 4 | WAV truncado: se recortan 16 000 bytes y la cabecera sigue declarando 496 000 cuadros | Rechazar por lectura incompleta | ✅ Rechazado: *"lectura incompleta con wave (976000 de 992000 bytes)"* |
| 5 | JSON `"completa"` con "salida procesable" en FALLA | Rechazar | ✅ Rechazado: *"la prueba 'salida procesable (mono, 16 kHz, PCM 16)' de la Etapa 1 no está en OK"* |
| 6 | JSON con estado desconocido (`"procesando"`) | Rechazar | ✅ Rechazado: *"estado de la Etapa 1 'procesando' (se espera 'completa' o 'grabando …')"* |
| 7 | WAV de 15 s, fuera del rango de 30 a 60 s | Rechazar por duración | ✅ Rechazado: *"dura 15.00 s, fuera de 30-60 s"* |
| 8 | JSON malformado (`{"estado": "completa", "pruebas": [`) | Rechazar por formato | ✅ Rechazado: *"el reporte … no es JSON válido"* |

Cada caso negativo comprueba con `pytest.raises(..., match=...)` que el rechazo ocurre **por el motivo esperado**, y no por cualquier error.

**Resultados.**

| Verificación | Resultado |
|---|---|
| `pytest PoC/paso2_diarizacion -k integracion` | **8 aprobados, 0 fallidos** (97 deseleccionados) |
| Suite completa de nivel 1 (`pytest PoC/paso2_diarizacion`) | **100 aprobados, 0 fallidos** (5 deseleccionados: niveles 2 y 3) |
| **No se ejecutó pyannote** | Confirmado. Al correr solo `test_integracion_sintetica.py` en un proceso aparte, `sys.modules` no contiene `pyannote`, `torch`, `torchaudio` ni `torchcodec`. Los 8 tests tardan 0,19 s |
| Grabaciones originales | 36 archivos en `PoC/paso1_captura/grabaciones/` (con subcarpetas) antes y después, **0 modificados** (SHA-256) |
| `openspec validate etapa-2-diarizacion --strict` | Válido |

**Problemas encontrados y corrección.** En la primera corrida fallaron los casos 3 y 8 con `TypeError: 'NoneType' object is not callable`. El error estaba **en el helper del test**, no en el bloque A: el diccionario que arma los reportes mapeaba `None` a `None` y después lo llamaba como función. Se corrigió para que `reporte=None` no escriba ningún `.json`, y los 8 casos pasaron.

**Conclusión.** La tarea 5.4 se cumple. Los cuatro casos que pide `tasks.md` (completo, interrumpido, sin reporte y WAV truncado) y los cuatro adicionales aprobados (salida procesable en FALLA, estado desconocido, duración fuera de rango y JSON malformado) pasan sin modelo, sin GPU, sin TorchCodec y sin FFmpeg, con el comando de verificación de la tarea.

---

## Tarea 5.5 — Verificación básica del nivel 2 y sus limitaciones

**Reformulación (decisión del 08/11/2026).**
- La tarea pedía originalmente una revisión manual, de oído, de cada reporte de integración.
- Se reemplazó por una **verificación automática básica**, porque las tres grabaciones se diseñaron con una secuencia de hablantes conocida (A · B · A, o una sola voz). Sirven para comprobar la integración y un comportamiento básico, no para evaluar con rigor la precisión de pyannote. Además, no es razonable validar de oído segmentos de 0,1–0,3 s.
- El Excel de revisión manual (`tests/reportes/revision_manual_diarizacion.xlsx`) quedó sin completar y se **eliminó**: era auxiliar, ningún test lo usaba, y su presentación por segmentos o por bloques partía de la secuencia conocida.
- La evaluación de calidad pasa al nivel 3 (Figshare, con referencia anotada).

**Verificación.** Está en la tabla "Verificación básica del nivel 2 (tarea 5.5)" de `PoC/paso2_diarizacion/README.md`, con una fila por grabación: auriculares, parlantes e interrumpida.
- Los datos salen de `tests/reportes/integracion_*.json` y de `nivel2/<nombre>/diarization.json`, de la corrida de la tarea 5.3.
- **Predominante por bloque:** en cada bloque de unos 15 s de la secuencia diseñada se suma, por speaker, el solapamiento de sus segmentos con el bloque.
- **Anomalías:** segmentos de menos de 0,5 s, superposiciones, tiempo de un speaker no predominante en un bloque y desvíos de más de 0,5 s en un cambio.
- El cálculo se hizo con un script auxiliar que no se versiona, sobre esos JSON. Los valores se pueden reproducir desde los JSON con la regla descrita.

| Comprobación | Auriculares | Parlantes | Cierre forzado |
|---|---|---|---|
| Hablantes esperados / detectados | 2 / 2 | 2 / 2 | 1 / 1 |
| Bloques con el predominante coherente con la secuencia | 3 de 3 | 3 de 3 | 3 de 3 |
| Reidentificación de A | sí | sí | — |
| Anomalías automáticas | 12 | 4 | 0 |
| Mayor desvío en un cambio | 1,01 s | 3,29 s | — |

**Resultado:** el comportamiento básico es correcto en las tres grabaciones. Las discrepancias pequeñas quedan documentadas como anomalías, sin validarlas de oído.

**Limitaciones (detalle en el README):**
- sesgo de diseño (la secuencia se conocía de antemano);
- sin referencia con tiempos exactos;
- muestra mínima (3 grabaciones, 2 hablantes como mucho, voz B de un video);
- condiciones de una sola máquina;
- no se miden DER, JER, confusión ni 3 o más hablantes.

**Conclusión:** la tarea 5.5 queda cumplida con su redacción nueva. **El nivel 2 queda cerrado como validación técnica más verificación básica**, no como evaluación de calidad.

## Conclusiones

1. El flujo **Etapa 1 → Etapa 2** funciona en la máquina de desarrollo sin GPU:
   - el WAV de la interfaz se acepta sin conversión;
   - FFmpeg 7.1.1 lo decodifica a través de TorchCodec;
   - pyannote corre en CPU;
   - el `diarization.json` cumple el contrato;
   - los archivos de la Etapa 1 quedan intactos.
2. Con turnos largos y separados, el modelo detecta la cantidad correcta de hablantes **sin `num_speakers`** y reidentifica a la misma persona. Pasa en los tres casos con turnos controlados:
   - las dos voces por el micrófono (prueba 2);
   - una voz local por el micrófono y una remota por la Mezcla estéreo, con auriculares (prueba 3);
   - ídem, con parlantes (prueba 4).
3. Con la voz remota por el sistema, los cambios de turno son menos limpios que en la prueba 2 (0,71 s y 0 s de superposición):
   - con auriculares (prueba 3): desviación de hasta 0,96 s, 0,41 s de superposición y 4 microsegmentos;
   - con parlantes (prueba 4): sin superposiciones ni microsegmentos, pero con una desviación de **2,09 s** en un cambio de turno, de causa no determinada.

   En las dos el error total ronda el 5–6 % del habla. Para estos escenarios, el nivel del sistema es crítico: con volumen bajo, la Mezcla estéreo no superó el umbral de la Etapa 1 (intento descartado `09_17_12`).
4. Con parlantes, en esta notebook **no se observó eco** en la mezcla. Hubo, en cambio, dos **incidencias de captura de la Etapa 1**: pérdida de 0,124 s y deriva de 0,141 s. Conviene comunicárselas a quien sea responsable de la Etapa 1 y ver si se repiten.
5. **Cierre forzado (prueba 5):**
   - la Etapa 1 deja un WAV procesable, con una pérdida de ≈ 0,3 s (como mucho 1,3 s), y un JSON en "grabando";
   - la Etapa 2 lo diariza sin problemas;
   - la prueba reveló que la regla original de normalización descartaba el último tramo de habla cuando la grabación termina mientras alguien habla. Se corrigió en la tarea 2.4, con un test de regresión.
6. Con habla entremezclada y sin referencia (prueba 1), el resultado queda **sin confirmar**. Una posible fusión de hablantes es justo el caso borde 2.1.2, que en la PoC se corrige en la Etapa 4 al etiquetar.
7. El tiempo en CPU fue de 1,5 a 2,5 veces la duración del audio (68 a 112 s para unos 45 s, y 74,6 s para 32,5 s).
8. **El nivel 2 está cerrado** (tareas 5.1 a 5.5) como validación técnica más verificación básica. La evaluación de calidad, con DER, JER, componentes, cantidad de hablantes y una corrida diagnóstica con `num_speakers=2`, queda para el nivel 3, con Figshare.
