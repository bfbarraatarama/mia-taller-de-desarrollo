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

## Nivel 2 · happy path (17/11/2026)

Reunión de prueba del #14 (OSM LatAm, 339 s, SHA-256 `c9377dd2…`) reproducida por el audio del sistema y grabada con la captura de la aplicación (`resultados/happy_path.json`).

| | Resultado |
|---|---|
| Grabación | Guardada en el directorio elegido: 350,04 s, estado «completa»; reproducción de 14:50:53 a 14:56:32 |
| Captura | Sistema −30,9 dBFS RMS (pico −8,7); sin pérdidas (0,005 s faltantes, 0 desbordes); sin desincronización; salida procesable |
| Micrófono | −∞ dBFS (muestras en cero) durante los 350 s. El operador declara que la grabación se hizo en un lugar muy silencioso y sin habla local. La prueba «ambas fuentes registran señal» queda en FALLA por el micrófono; no afecta el contenido procesado |
| Proceso | Completado en 215,4 s (diarización 33,9 s, transcripción 58,5 s, minuta 122,5 s): 3 hablantes y 49 intervenciones (con el WAV directo, corrida 01 del #14: 3 y 52); minuta con 2 temas, 1 decisión, 2 problemas y 3 acciones |
| Calidad y varios archivos | En el #14, corridas 01 y 02 (WAV directo): no cumple en ninguna modalidad (`calidad.md`). La minuta de esta grabación no tiene evaluación independiente |
| Pendiente manual | Grabación desde la interfaz y, por separado, avance de cada etapa y fichas al procesar la reunión desde la interfaz |

Observación: el responsable de la acción del foro sale «Rafael» en esta corrida (sin fichas, el nombre lo toma el modelo del habla) y «Jorge» en la corrida 01 del #14, donde el operador nombró las fichas; en el audio, Marta le dice «Rafael» a ese hablante. Lo juzga la evaluación de calidad del #14.

## Nivel 2 · 2.1.1 terminología especializada (17/11/2026)

Transcripción de la corrida 01 del #14 (WAV directo de OSM LatAm; `resultados/terminologia.json`): audio conservado con su SHA-256 y sin adaptación terminológica (Whisper sin prompt inicial ni vocabulario propio). Términos: Discourse, la plataforma del foro, sale «discurso» y «discurs» (00:21 y 01:14); OpenStreetMap, mapatón, notatón, wiki, Telegram, TikTok, Instagram, Mapillary, stickers, logo contest y podcasts salen bien; StreetComplete sale en dos palabras; dos fragmentos dudosos (04:19 y 05:00). Sin transcripción de referencia: la lista la confirma el tercero.

## Pendiente

- Recorrido del tercero (`evaluacion/escenarios/PROTOCOLO.md`): las comprobaciones manuales y la confirmación con la aplicación abierta.
- Confirmaciones del tercero para el happy path (interfaz) y para la lista de términos de 2.1.1.
