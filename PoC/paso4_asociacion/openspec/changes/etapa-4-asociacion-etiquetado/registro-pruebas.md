# Registro de pruebas · Etapa 4

Niveles de D9 (`design.md`). Fecha de las corridas: 11/11/2026, sobre la rama `feature/etapa-4-asociacion`.

## Entornos

| Entorno | Versiones | Uso |
|---|---|---|
| Interfaz (`.venv` de la raíz) | Fedora 43, Python 3.14.8, PySide6 6.12.0, NumPy 2.5.3, SciPy 1.18.1, espeak-ng 1.51.1 | Nivel 1 completo, diálogo sin pantalla (`QT_QPA_PLATFORM=offscreen`) |
| Orquestador (`uv run --python 3.12`) | Python 3.12.13, pydantic, NumPy, SciPy, soundfile; sin PySide6 | Nivel 1 sin el diálogo, más las pruebas cruzadas con el código de las Etapas 2 y 5 |

Código de las otras etapas usado en las pruebas cruzadas, extraído de sus ramas con `git archive` (sin tocar el repositorio):

| Etapa | Rama · commit | Qué se usa |
|---|---|---|
| 2 (#8) | `feature/etapa-2-diarizacion` · `81d8563` | `contrato.py` y las 25 hipótesis de S26 (`ETAPA2_DIR`) |
| 5 (#6) | `poc-paso5-minutas` · `3897ca3` | `src/minutas/entrada.py` y `contratos.py`, sin su `__init__` (`ETAPA5_SRC`) |

## Nivel 1 · pruebas unitarias

Un test por escenario de las specs, con el mismo nombre, más casos de control.

| Archivo | Tests | Cubre |
|---|---:|---|
| `test_contrato_entradas.py` | 26 | Audio, `diarization.json` (igual a la Etapa 2), `asr.json` con margen y recortes |
| `test_asociacion.py` | 17 | D1, D4, contrato de `transcription.json`, ejemplo ideal |
| `test_atribucion.py` | 21 | D2, D3, D5 con valores límite, entradas sin habla, 8 hablantes |
| `test_fragmentos.py` | 15 | D6: tramos solos, candidatos, semilla entre procesos, recorte, respaldos, texto |
| `test_etiquetado.py` | 32 | Modelo de las fichas, nombres, cierre, `speakers.json` |
| `test_salida.py` | 17 | Escritura con respaldo y reversión, meta, errores, CLI, rutas |
| `test_fichas.py` | 18 | Diálogo: cableado con el modelo y reproductor falso |
| `test_ejemplo_ideal.py` | 11 | Generador del ejemplo ideal y del guion manual |
| **Total** | **157** | |

| Entorno | Resultado medido |
|---|---|
| Interfaz, 3.14 | 153 pasan · 4 se saltean (las cruzadas, sin las ramas de las otras etapas) |
| Orquestador, 3.12, con las ramas de las Etapas 2 y 5 | 139 pasan · 1 módulo se saltea (`test_fichas.py`, sin PySide6) |

Pruebas cruzadas incluidas en la corrida de 3.12:

| Prueba | Resultado |
|---|---|
| `validar_diarizacion` propio contra el de la Etapa 2, sobre las 25 hipótesis de S26 y una inválida | Mismas violaciones, mensaje por mensaje |
| Tramos solos sobre las 25 hipótesis de S26 contra la medición de D6 | 49 hablantes, 16 sin tramo solo, mediana de las medias 1,99 s (0,92 a 4,30 s) |
| `leer_transcripcion` de la Etapa 5 sobre `transcription.json`, sin nombres y con nombres | Lo acepta en los dos casos |

## Lista de chequeo manual (tarea 10.1)

Lo que el nivel 1 no puede comprobar: oír el audio y usar el mouse. Se hace en la máquina de referencia, con audio.

```bash
cd PoC/paso4_asociacion
PY="$(git rev-parse --show-toplevel)/.venv/bin/python"
"$PY" ejemplo_ideal/generar.py --guion ejemplo_ideal/guion_manual.json --salida ejemplo_ideal/generado/manual
"$PY" fichas.py ejemplo_ideal/generado/manual
```

El guion manual tiene 8 hablantes. Hugo (`SPEAKER_04`) solo dice «Sí, totalmente de acuerdo.» encima de Diego (`SPEAKER_03`), así que nunca habla solo.

| # | Escenario (spec) | Qué hacer | Qué tiene que pasar | Resultado |
|---|---|---|---|---|
| 1 | Ocho fichas | Abrir el diálogo y achicar la ventana | Hay 8 fichas, de mayor a menor tiempo de habla; aparece la barra y se llega a todas | |
| 2 | Aviso de superposición | Mirar la ficha de `SPEAKER_04` | Muestra el aviso de que se oye otra voz; las otras 7 no | |
| 3 | Reproducción del fragmento | ▶ en la primera ficha | Suena solo ese fragmento y al terminar el botón vuelve a ▶ solo | |
| 4 | Una reproducción a la vez | ▶ en una ficha y enseguida ▶ en otra | La primera se corta y suena solo la segunda | |
| 5 | Detener | ■ mientras suena | Se corta y el botón vuelve a ▶ | |
| 6 | Otro fragmento | En `SPEAKER_00`, «Otro fragmento» | Cambian el contador, los tiempos y el texto | |
| 7 | Autocompletado | Escribir «Ana» en una ficha y «A» en otra | Se ofrece «Ana» | |
| 8 | Nombres que difieren solo en tildes | «Martín» y «Martin» en dos fichas, y Confirmar | Avisa; con «Volver a las fichas» no se cierra | |
| 9 | Volver a las fichas | Cerrar con la X y presionar Enter | Vuelven las fichas con los nombres escritos | |
| 10 | Seguir sin nombres | Cerrar con la X y elegir esa opción | Código de salida 0; `transcription.json` con `name: null` y sin `speakers.json` | Pasa (11/11): código 0, los 9 `name` en `null`, `etiquetado: false` en el meta y se borró el `speakers.json` de la corrida anterior |
| 11 | Cancelar | Cerrar con la X y elegir «Cancelar» | Código de salida 2; no se escribe nada | Pasa (11/11): código 2; los archivos conservan la hora de la corrida anterior y el SHA-256 de `transcription.json` coincide con el del meta |
| 12 | Fragmento en pantalla al confirmar | «Otro fragmento» dos veces en `SPEAKER_00`, nombres y Confirmar | `speakers.json` tiene el tercer fragmento de `SPEAKER_00` y los nombres en `transcription.json` | A repetir: la corrida del 11/11 terminó con código 0, pero la del escenario 10 sobrescribió su salida antes de revisarla |
| 13 | Grabar durante el etiquetado | Desde el panel del paso 1, con las fichas abiertas | Grabar y Procesar no responden | Pendiente: grupo 7 |

Salida del guion manual: 9 intervenciones de 7 etiquetas. La frase de Hugo queda en `SPEAKER_03` (Diego) con `overlap` y `ambiguous`: Hugo tiene ficha pero ninguna intervención propia, porque nunca habla solo.

## Nivel 2 · integración con datos reales (grupo 8)

Corrida del 11/11/2026 en la máquina de referencia, con la GPU libre. Las 4 grabaciones propias de la Etapa 1 (`PoC/paso1_captura/grabaciones/`, 16 kHz, mono, PCM16; no se versionan) se copiaron como `audio.wav` en una carpeta por reunión, fuera del repositorio. Las salidas son derivados de esas grabaciones y tampoco se versionan.

| Entorno | Versiones |
|---|---|
| GPU | NVIDIA RTX 3050 Laptop 6 GB, driver 580.178.04 |
| Etapas 2 y 3 (venv propio, Python 3.12.13) | torch 2.8.0+cu128, torchaudio 2.8.0, torchcodec 0.7.0, pyannote.audio 4.0.7, openai-whisper 20250625, FFmpeg 7.1.5 del sistema; instalado con `requirements.txt` + `constraints.txt` de la Etapa 2 y `openai-whisper` con las mismas restricciones |
| Etapa 4 | `.venv` de la interfaz (Python 3.14.8) |
| Etapa 5 (solo lectura) | `uv run --python 3.12` con pydantic |

| Etapa | Código | Comando por reunión |
|---|---|---|
| 2 | `feature/etapa-2-diarizacion` · `81d8563` | `python diarizar.py CARPETA/audio.wav --salida CARPETA --device cuda` |
| 3 | `main` · `ac567e2` (`src/STT`, modelo por defecto `medium`) | `python -m STT CARPETA/audio.wav -o CARPETA/asr.json --device cuda` |
| 4 | `feature/etapa-4-asociacion` · `e1ec0c1` | `python asociar.py CARPETA` |
| 5 | `main` · `ac567e2` | `minutas.entrada.leer_transcripcion(CARPETA/transcription.json)` |

`verificar_entorno.py --gpu` de la Etapa 2: 0 fallas, 1 aviso (paquetes de Whisper fuera de su lock).

### 8.1 · Etapas 2 y 3 en CUDA

| Reunión | Duración (s) | Etapa 2: hablantes | Etapa 2: segmentos | Etapa 2: tiempo (s) | Etapa 2: VRAM pico (MiB) | Etapa 3: segmentos | Etapa 3: tiempo de proceso (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026_10_29_20_33_46 | 6,0 | 2 | 3 | 6,9 | 190,9 | 1 | 167,2 * |
| 2026_10_29_21_19_59 | 30,4 | 2 | 13 | 6,2 | 1628,5 | 9 | 12,7 |
| 2026_11_03_19_53_47 | 212,5 | 3 | 115 | 18,7 | 1628,8 | 99 | 37,6 |
| 2026_11_03_19_58_10 | 50,7 | 3 | 34 | 7,5 | 1628,8 | 11 | 13,5 |

\* Incluye la descarga del modelo `medium`. Tiempo de la Etapa 2: `tiempo_s` de `diarization.meta.json`. Tiempo de la Etapa 3: reloj del proceso completo (carga del modelo incluida).

Pruebas de la Etapa 2 en este entorno, para sus tareas 7.3 y 7.4:

| Suite | Resultado |
|---|---|
| Nivel 1 | 244 pasan, 2 omitidas (un caso solo para máquinas sin GPU; resultados publicados sin la referencia local de Figshare) |
| Nivel 2 (`-m slow`, `DIARIZACION_AUDIOS_CPU` con las grabaciones de 30,4 s y 50,7 s y sus reportes de la Etapa 1) | 5 pasan |
| `-m gpu` | 1 omitida: falta el dataset de Figshare preparado; el test de memoria de su tarea 7.3 todavía no existe |

### 8.2 · Etapa 4 y lectura por la Etapa 5

| Reunión | `asociar.py` | Violaciones de `validar_transcripcion` | Recortes de `asr.json` | Intervenciones leídas por la Etapa 5 |
|---|---|---:|---:|---:|
| 2026_10_29_20_33_46 | código 0 | 0 | 0 | 1 |
| 2026_10_29_21_19_59 | código 0 | 0 | 0 | 9 |
| 2026_11_03_19_53_47 | código 0 | 0 | 0 | 117 |
| 2026_11_03_19_58_10 | código 0 | 0 | 0 | 11 |

Contrato al 100 % en las 4 reuniones. La Etapa 5 solo leyó la entrada; no se generaron minutas.

### 8.3 · Marcas y reglas de decisión

Umbrales sin cambiar (`transcription.meta.json`: `hueco_max_s` 0,25 · `overlap_min_s` 0,2 · `segundo_hablante_min` 0,3 · `propio_min` 0,5). Conteos de `conteos` del meta.

| Reunión | Intervenciones | Con `overlap` | Con `ambiguous` | Sin hablante | Palabras | Por D2 (empate) | Por D3 (hueco) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026_10_29_20_33_46 | 1 | 1 (100 %) | 0 (0 %) | 0 | 10 | 0 (0 %) | 0 (0 %) |
| 2026_10_29_21_19_59 | 9 | 1 (11 %) | 1 (11 %) | 0 | 46 | 2 (4,3 %) | 1 (2,2 %) |
| 2026_11_03_19_53_47 | 117 | 47 (40 %) | 53 (45 %) | 2 | 443 | 104 (23,5 %) | 4 (0,9 %) |
| 2026_11_03_19_58_10 | 11 | 2 (18 %) | 2 (18 %) | 1 | 72 | 1 (1,4 %) | 1 (1,4 %) |
| **Total** | **138** | **51 (37 %)** | **56 (41 %)** | **3** | **571** | **107 (18,7 %)** | **6 (1,1 %)** |

La reunión de 212,5 s concentra el 92 % de las marcas `overlap` y el 97 % de las palabras decididas por D2. Sin referencia anotada de estas grabaciones, no se mide si esas decisiones aciertan.

## Nivel 3 · muestra congelada (grupo 9)

Pendiente: depende de la muestra congelada (semana 7).
