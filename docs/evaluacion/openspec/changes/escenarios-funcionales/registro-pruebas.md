# Registro de pruebas

Escenarios de §2.1 y recuperación ante interrupciones (issue #15). Máquina de referencia: Fedora 43, RTX 3050 Laptop 6 GB; mismo entorno que la evaluación modular (`docs/evaluacion/openspec/changes/evaluacion-modular/registro-pruebas.md`). Código: `main` con el #19 y el #20.

## Nivel 1 · pruebas automáticas

`tests/evaluacion/test_escenarios_*.py`: 14 pruebas, con los escenarios de la spec (Ruido reproducible, Entrada alterada, Seis o más hablantes, Minuta por fragmentos, Comprobación solo visual, Corte forzado). La de corte forzado usa una captura falsa que escribe el WAV como la real.

## Nivel 2 · corridas con la aplicación (16/11/2026)

Entradas fijadas en `evaluacion/escenarios/entradas.manifest.json`. El ruido de 2.1.4 se armó dos veces con el mismo SHA-256 (`7b5a86d3…`).

| Escenario | Entrada | Tiempo | Comprobaciones automáticas | Manual pendiente |
|---|---|---|---|---|
| 2.1.2 Voces y superposición | Figshare S25-12 (4,2 min) | 252 s | Sí: audio conservado; 15,2 s con dos o más etiquetas; 48 `ambiguous` y 23 `overlap` de 69 intervenciones | Mismo nombre en dos etiquetas |
| 2.1.3 Seis o más hablantes | ICSI Bro015 (16,9 min, 6 hablantes) | 602 s | Sí: audio conservado; 6 etiquetas detectadas; las 21 intervenciones sin hablante, marcadas como ambiguas (60 ambiguas en total) | Una ficha por hablante |
| 2.1.4 Ruido | Figshare S22-01 con ruido rosa a 5 dB de SNR | 62 s | Sí: audio conservado; pipeline completo; transcripción y minuta presentes | — |
| 2.1.5 Más largo que el contexto | Figshare S25 completa, 30 archivos en orden (unos 35 min) | 3605 s | Sí: 30 de 30 fuentes conservadas; una sola transcripción; minuta en 27 bloques de extracción, 35 llamadas al modelo, 2 niveles de consolidación (minuta: 2865 s) | — |

Las comprobaciones automáticas verifican lo que se ve en los archivos; la calidad de la transcripción y de la minuta con ruido o en inglés no se evalúa en este issue (§2.1.4: «sin garantizarlos»).

## Nivel 2 · recuperación ante interrupciones (16/11/2026)

`pw-jack .venv/bin/python -m evaluacion.escenarios recuperacion`: captura de la aplicación en modo automático (PipeWire/JACK, micrófono y audio del sistema), cortada con SIGKILL.

| | Resultado | §2.3 |
|---|---|---|
| Grabado hasta el corte | 130,0 s | 2 min o más |
| Duración del WAV que quedó | 129,75 s | |
| Perdido | 0,25 s | 5 s o menos: cumple |
| WAV válido | Sí | |
| Listado como interrumpido (`consultar_grabaciones_interrumpidas`) | Sí; el `.json` quedó con estado «grabando» | |
| Procesable | Sí: el pipeline lo procesó completo, con minuta | |
| La aplicación lo ofrece al reiniciar | Pendiente del recorrido del tercero | |

## Pendiente

- Recorrido del tercero (`evaluacion/escenarios/PROTOCOLO.md`): las comprobaciones manuales y la confirmación con la aplicación abierta.
- Happy path (reunión de prueba del #14) y 2.1.1 (grabación con terminología especializada).
