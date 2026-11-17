# Tasks

## 1. Preparación del audio de prueba compartido

- [x] 1.1 Generar el audio de ejemplo ideal con `python -m evaluacion.asociacion.ejemplo_ideal.generar` y verificar que el directorio `evaluacion/asociacion/ejemplo_ideal/generado/` contiene `audio.wav`, `diarization.json`, `asr.json` y `referencia.json` con duración entre 55 y 80 segundos
- [x] 1.2 Verificar que el audio de prueba es reproducible ejecutando el generador dos veces y comprobando que los `audio.wav` resultantes son byte-idénticos (confirma que el flag `-D` de espeak-ng funciona en este entorno)

## 2. Validación del flujo principal — Windows/CPU (Luisa)

- [x] 2.1 Procesar `evaluacion/asociacion/ejemplo_ideal/generado/audio.wav` con `python -m src.pipeline <ruta_audio>` y verificar que el directorio de salida contiene `workflow.json` con `"estado": "completado"` y los 7 archivos de salida esperados (`audio.wav`, `ingesta.json`, `diarization.json`, `asr.json`, `transcripcion.json`, `minutes.json`, `minutes.md`)
- [x] 2.2 Verificar que `minutes.md` contiene texto de transcripción y al menos dos nombres de hablantes diferentes, y que `minutes.json` tiene un campo `resumen` no vacío — registrar el contenido generado como evidencia
- [x] 2.3 Procesar un archivo MP3 (cualquier grabación de voz de más de 10 segundos) y verificar que el pipeline lo ingesta y produce `audio.wav` a 16 kHz mono PCM 16 (usar `python -c "import soundfile as sf; print(sf.info('<ruta>/audio.wav'))"`)
- [x] 2.4 Procesar el mismo directorio de salida del paso 2.1 nuevamente y verificar que el sistema detecta el resultado vigente y no reprocesa (el `workflow.json` mantiene las fechas de las etapas originales sin actualizarse)

## 3. Validación de captura y reproducción — Windows/CPU (Luisa)

- [x] 3.1 Ejecutar `python -m src.captura --listar` y verificar que lista al menos un micrófono disponible sin error
- [x] 3.2 Ejecutar `python -m src.captura --duracion 15 --tono` y verificar que se crea un archivo WAV de ~15 segundos a 16 kHz mono PCM 16 con un tono audible en los primeros segundos (verificar con `sf.info()`)
- [x] 3.3 (Opcional si hay dispositivo de audio del sistema) Capturar audio del sistema junto al micrófono usando la GUI, reproducir un audio desde el sistema durante la grabación y verificar que el WAV resultante tiene señal en ambas fuentes
- [x] 3.4 *(parcial — ver nota de cierre)* Abrir la GUI con `python -m src.interfaz`, iniciar una grabación de 20 segundos desde micrófono y detenerla, luego usar el control de reproducción de la interfaz para verificar que el audio se escucha correctamente

## 4. Validación de resiliencia — Windows/CPU (Luisa)

- [x] 4.1 Iniciar el procesamiento de un archivo de audio largo (> 60 segundos) desde la GUI y cancelarlo durante la etapa `diarizar`; verificar que `workflow.json` queda con `"estado": "cancelado"` y que no hay archivos `.tmp` ni parciales en el directorio de salida
- [x] 4.2 Reanudar el procesamiento del directorio del paso 4.1 y verificar que el pipeline retoma desde la etapa `preparar` (la única completada antes de la cancelación) sin reprocesar la ingesta, completando exitosamente
- [x] 4.3 Iniciar procesamiento, terminar el proceso abruptamente con Task Manager (o `taskkill /F /PID <pid>`), relanzar sobre el mismo directorio y verificar que el sistema detecta el checkpoint inconsistente, lo descarta y reanuda correctamente
- [x] 4.4 *(parcial — ver nota de cierre)* Mover el archivo de audio original a otra carpeta después de completar la ingesta, luego intentar reprocesar desde cero con la ruta original; verificar que el sistema usa la copia conservada en el directorio de la reunión (mensaje de log o ausencia de error)
- [x] 4.5 Lanzar dos instancias del pipeline sobre el mismo directorio (desde dos terminales) y verificar que la segunda falla con un mensaje que contiene "ocupada" o "ReunionOcupada" sin corromper el estado de la primera

## 5. Validación en Linux/CPU y Linux/GPU (compañeros)

- [ ] 5.1 [Linux/CPU] Generar el audio de ejemplo ideal y procesar el flujo principal completo (equivalente a tareas 1.1, 2.1, 2.2) — registrar plataforma, versiones de dependencias y resultado
- [x] 5.2 [Linux/GPU] Generar el audio de ejemplo ideal y procesar el flujo principal completo con perfil CUDA — registrar plataforma, GPU, VRAM utilizada y resultado *(validado con audio sintético del ejemplo_ideal; sin verificación con grabación real de reunión)*
- [x] 5.3 [Linux/GPU] Verificar que el hallazgo crítico de Matías Caccia (#4: torchcodec cu128 + libnppicc.so.12) está documentado como pendiente de corrección con responsable asignado en `PR_ISSUE_18.md`
- [x] 5.4 [Linux] Ejecutar `pytest tests/ -q` completo en Linux y verificar que el resultado es 752 passed (o documentar cualquier diferencia con causa identificada)

## 6. Documentación de resultados y cierre de issue

- [x] 6.1 Completar la tabla de evidencias en `PR_ISSUE_18.md` con los resultados de Windows/CPU: fecha, escenarios ejecutados, resultado (éxito/fallo/parcial), y observaciones para cada tarea del grupo 2–4
- [x] 6.2 Registrar en `PR_ISSUE_18.md` los resultados de Linux recibidos de los compañeros con autor, fecha y plataforma
- [x] 6.3 Verificar que todos los criterios de cierre de la issue #18 están marcados: (a) matriz de configuraciones evaluadas, (b) procedimientos comprobados, (c) verificaciones automatizadas reutilizables ✅, (d) incompatibilidades resueltas o registradas con responsable, (e) documentación actualizada

## Workflow follow-up

- Archivar el change (`openspec-archive-change`) una vez completadas todas las tareas del grupo 6.
- Los hallazgos de instalación de Matías Caccia (torchcodec/cu128, 7zip/RAR en Fedora, README Fedora) se coordinan en un issue separado o en una nueva iteración de esta issue; no bloquean el archivo de este change.

## Nota de cierre (2026-11-16)

Los grupos 1–4 (Windows/CPU), 5.2–5.4 (Linux/GPU) y 6 (documentación) están completados. El change se archiva en este estado.

**Tarea 5.1 (Linux/CPU) — pendiente de coordinación con el equipo.** No bloquea el cierre de esta etapa: la decisión D2 del diseño establece que cada responsable trabaja en su entorno sin bloquear al otro, y la decisión D4 permite cerrar con nota sobre los pendientes Linux cuando requieren coordinación adicional.

**Validaciones parciales documentadas en `PR_ISSUE_18.md`:**
- Tarea 3.4 — reproducción desde GUI: el audio capturado es válido y audible, pero el control integrado de reproducción no pudo verificarse con `QT_QPA_PLATFORM=offscreen`.
- Tarea 4.4 — reanudación sin archivo original: la reutilización con directorio completamente vigente fue confirmada; el reprocesamiento via `fuentes/` (directorio parcialmente vigente + audio original ausente) no fue ejercitado.

**Suite automatizada posterior a la actualización de `main` con correcciones de compatibilidad (2026-11-16):** 910 passed, 0 failed, 7 skipped, 6 deselected, 52 subtests — 515,76 s.
