# Proposal

## Why

La issue #18 requiere validar que la aplicación funciona de extremo a extremo en distintas configuraciones de hardware y sistema operativo. La suite automatizada (752 tests en Windows/CPU) verifica la corrección del código, pero no reemplaza la ejecución real de la aplicación: capturar audio, procesar una reunión completa y obtener una minuta nunca ha sido validado como flujo integrado en el contexto de esta issue. Sin esta validación no se pueden cerrar los criterios de "procedimientos comprobados" y "evaluación de captura, reproducción, procesamiento y persistencia" que la issue exige.

## What Changes

- Se define qué escenarios funcionales deben ejecutarse, en qué orden, con qué entradas y qué resultados se consideran correctos.
- Se establece la separación de responsabilidades: Windows/CPU a cargo de Luisa, Linux/CPU y Linux/GPU a cargo de los compañeros del equipo.
- No se modifica código de producción ni tests. Los hallazgos de instalación de Matías Caccia (Fedora/cu128) se registran como pendientes de coordinación, fuera del alcance de este cambio.
- El resultado es un conjunto de escenarios de prueba manual referenciables, con criterios de aceptación por plataforma.

## Capabilities

### New Capabilities

- `validacion-funcional/flujo-principal`: Procesamiento completo de un archivo de audio pre-grabado a través del pipeline (preparar → diarizar → transcribir → asociar → minuta) y verificación de la persistencia de los archivos de salida en disco.
- `validacion-funcional/captura`: Captura de audio en vivo desde micrófono o audio del sistema, y reproducción del audio capturado.
- `validacion-funcional/resiliencia`: Cancelación de un procesamiento en curso y recuperación ante errores e interrupciones (proceso cortado, archivo de entrada movido, reinicio tras fallo).

### Modified Capabilities

(ninguna — no hay specs existentes en este proyecto)

## Impact

- **Código afectado (solo lectura en este cambio):** `src/pipeline/ejecucion.py`, `src/pipeline/configuracion.py`, `src/captura/captura.py`, `src/captura/recuperacion.py`, `src/interfaz/interfaz.py`, `src/interfaz/panel_procesamiento.py`
- **Archivos de salida del pipeline:** `workflow.json`, `audio.wav`, `ingesta.json`, `diarization.json`, `asr.json`, `transcription.json`, `minutes.json`, `minutes.md`
- **Plataformas en scope:** Windows 11 / CPU (sin GPU); Linux/CPU y Linux/GPU como validación a cargo de compañeros
- **Dependencias externas usadas en la validación:** espeak-ng (pruebas de ejemplo ideal ya resueltas), ffmpeg, libarchive, sounddevice, pyannote, Whisper
- **Fuera de scope:** corrección de los hallazgos de instalación en Fedora/cu128 reportados por Matías Caccia (torchcodec/libnppicc, 7zip/RAR, README Fedora); esos se registran como pendientes externos
