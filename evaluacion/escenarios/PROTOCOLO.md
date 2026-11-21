# Protocolo para recorrer los escenarios (issue #15)

Lo hace **una persona que no ejecutó las corridas**, con la aplicación abierta, como pide §2.3 («un tercero recorre los escenarios con la aplicación abierta y marca sí o no»). Para cada «Entonces» de §2.1, marcar **sí** o **no** en la columna «Tercero» y anotar lo que haga falta en «Observaciones». Al terminar, commitear este archivo marcado.

Las comprobaciones automáticas ya corridas están en [`resultados/escenarios.json`](resultados/escenarios.json) y [`resultados/recuperacion.json`](resultados/recuperacion.json). Este recorrido no las reemplaza: confirma lo que se ve en la interfaz y lo que las automáticas no pueden juzgar.

## Preparación

Desde la raíz del repositorio, con el entorno único instalado:

```bash
.venv/bin/python -m evaluacion.modular preparar --verificar   # la muestra congelada está intacta
.venv/bin/python -m evaluacion.escenarios preparar             # arma y fija las entradas (manifiesto entradas.manifest.json)
pw-jack .venv/bin/python -m src.interfaz                       # abre la aplicación (en Windows, sin pw-jack)
```

En la aplicación, elegir como directorio de salida una carpeta nueva por escenario. En «Procesar reunión», cargar los archivos indicados **en el orden indicado** y procesar. Completar las fichas de hablantes cuando aparezcan.

## Escenarios

| Escenario | Entrada | «Entonces» de §2.1 | Automático | Tercero (sí/no) | Observaciones |
|---|---|---|---|---|---|
| Happy path · grabación | Cualquier audio que suene por el sistema | Grabar unos 30 s desde la interfaz en un directorio elegido: queda guardada ahí. Comprobación aparte del procesamiento: no es un recorrido único de grabar y procesar; ese recorrido se hizo por línea de comandos (`happy_path.json`) | manual | | |
| Happy path · procesamiento | `evaluacion/integral/muestras/osm-latam-20220730/audio.wav` (reunión de prueba del #14), cargado desde la interfaz | Se ve el avance de cada etapa | manual | | |
| | | Aparece una ficha por hablante con fragmento de audio y texto; escuchar y escribir el nombre. Comprobar que el nombre corresponde a quien habla (en el audio, Marta le dice «Rafael» a uno de ellos) | manual | | |
| | | Transcripción con nombres y marcas temporales; minuta con temas, decisiones y acciones con responsable y marca temporal | ver `happy_path.json` | | |
| | | Recupera los 2 temas y la acción sin inventar: **no** en las corridas 01 y 02 del #14; la misma reunión en varios archivos da una sola transcripción y una sola minuta | ver `calidad.md` del #14 | | |
| 2.1.1 Terminología | La misma reunión de OSM | Transcribe sin adaptación terminológica y conserva el audio | ver `terminologia.json` | | |
| | | Escuchar y confirmar la lista de términos de `terminologia.json` (por ejemplo, Discourse → «discurso») | manual | | |
| 2.1.2 Voces y superposición | `evaluacion/modular/datos/figshare/S25/12/audio.wav` | Conserva etiquetas, intervalos y solapamientos | ver reporte | | |
| | | Marca las intervenciones de hablante ambiguo (en el visor de la transcripción) | ver reporte | | |
| | | Si separa a una persona en dos etiquetas, ponerles el mismo nombre en las fichas: se tratan como una sola | manual | | |
| 2.1.3 Seis o más hablantes | `hito-2/.cache/icsi_audio/Bro015.interaction.wav` (ICSI, en inglés) | Etiqueta a cada hablante detectado: una ficha por etiqueta | ver reporte | | |
| | | Marca como ambiguas las intervenciones que no puede atribuir | ver reporte | | |
| | | Si no termina, lo informa y conserva el audio | ver reporte | | |
| 2.1.4 Ruido | `evaluacion/escenarios/datos/2.1.4/audio.wav` (ruido rosa, 5 dB de SNR) | Conserva el audio y los resultados, sin garantizarlos | ver reporte | | |
| | | Informa si alguna etapa falla | ver reporte | | |
| 2.1.5 Más largo que el contexto | Los 30 archivos `evaluacion/modular/datos/figshare/S25/01/audio.wav` a `30/audio.wav`, en orden | Procesa la minuta por fragmentos y consolida; si no puede, lo informa y conserva la transcripción | ver reporte | | |
| | | Una sola transcripción y una sola minuta para los 30 archivos | ver reporte | | |
| Error del sistema | Grabación de la prueba de recuperación: carpeta `evaluacion/escenarios/corridas/recuperacion/grabaciones/` | Queda un archivo procesable con lo grabado hasta el corte, salvo como máximo 5 s, marcado como interrumpido | ver reporte | | |
| | | Al reiniciar, la aplicación lista la grabación interrumpida y ofrece procesarla: elegir esa carpeta como salida, cerrar la aplicación y volver a abrirla | manual | | |

## Resultado

| | |
|---|---|
| Recorrido por | |
| Fecha | |
| Escenarios que hacen lo que dice su «Entonces» | de 7 |
| Recuperación (5 s o menos, procesable, listada al reiniciar) | sí / no |
