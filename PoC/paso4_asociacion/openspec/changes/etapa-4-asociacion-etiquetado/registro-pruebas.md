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
| 10 | Seguir sin nombres | Cerrar con la X y elegir esa opción | Código de salida 0; `transcription.json` con `name: null` y sin `speakers.json` | |
| 11 | Cancelar | Cerrar con la X y elegir «Cancelar» | Código de salida 2; no se escribe nada | |
| 12 | Fragmento en pantalla al confirmar | «Otro fragmento» dos veces en `SPEAKER_00`, nombres y Confirmar | `speakers.json` tiene el tercer fragmento de `SPEAKER_00` y los nombres en `transcription.json` | |
| 13 | Grabar durante el etiquetado | Desde el panel del paso 1, con las fichas abiertas | Grabar y Procesar no responden | Pendiente: grupo 7 |

## Nivel 2 · integración con datos reales (grupo 8)

Pendiente. El 11/11/2026 la GPU de la máquina de referencia (RTX 3050 de 6 GB) estaba ocupada por otro proceso (4,2 GB), así que no se corrieron las Etapas 2 y 3 sobre las 4 grabaciones propias. La Etapa 2 ya tiene resultados en GPU de otra máquina (RTX 4060 Ti, comentario de Bruno en #8), así que la tarea 8.1 se reduce a obtener `diarization.json` y `asr.json` de las grabaciones propias.

## Nivel 3 · muestra congelada (grupo 9)

Pendiente: depende de la muestra congelada (semana 7).
