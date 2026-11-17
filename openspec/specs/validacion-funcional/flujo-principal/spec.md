# validacion-funcional/flujo-principal Specification

## Purpose
Garantiza que el pipeline completo —desde un archivo de audio hasta la minuta generada— produce los artefactos correctos y los persiste en disco de forma duradera en todas las plataformas soportadas.

## Requirements

### Requirement: Pipeline completo desde archivo de audio
Dado un archivo WAV de entrada válido, el sistema SHALL ejecutar las cinco etapas del pipeline (preparar, diarizar, transcribir, asociar, minuta) en orden y producir todos los archivos de salida definidos.

#### Scenario: Ejecución exitosa en Windows/CPU
- **GIVEN** un archivo WAV de audio de una reunión (≥ 30 segundos, 16 kHz, mono, PCM 16)
- **WHEN** se inicia el procesamiento con perfil CPU desde la GUI o la CLI
- **THEN** el pipeline completa todas las etapas sin errores y el directorio de salida contiene `workflow.json` con estado `completado`, `audio.wav`, `ingesta.json`, `diarization.json`, `asr.json`, `transcription.json`, `minutes.json` y `minutes.md`

#### Scenario: Ejecución exitosa en Linux/GPU
- **GIVEN** un archivo WAV de audio de una reunión (≥ 30 segundos, 16 kHz, mono, PCM 16)
- **WHEN** se inicia el procesamiento con perfil GPU (CUDA) desde la GUI o la CLI
- **THEN** el pipeline completa todas las etapas sin errores y el directorio de salida contiene los mismos archivos que en Windows/CPU

#### Scenario: Ejecución exitosa en Linux/CPU
- **GIVEN** un archivo WAV de audio de una reunión (≥ 30 segundos, 16 kHz, mono, PCM 16)
- **WHEN** se inicia el procesamiento con perfil CPU desde la GUI o la CLI en Linux
- **THEN** el pipeline completa todas las etapas sin errores y el directorio de salida contiene los mismos archivos que en Windows/CPU

### Requirement: Contenido mínimo de la minuta generada
El archivo `minutes.json` SHALL contener exactamente las secciones solicitadas; las secciones no solicitadas no aparecerán en la salida. Cuando `resumen` esté entre las secciones solicitadas, su valor SHALL ser no vacío; las demás secciones seleccionadas pueden contener listas vacías si no hay elementos extraíbles. El archivo `minutes.md` SHALL ser la presentación ejecutiva del contenido de `minutes.json`. El archivo `transcription.json` (producido por la etapa `asociar`) es un artefacto intermedio distinto de la minuta: contiene los segmentos con hablante, nombre y texto, y sirve de entrada a la etapa `minuta`.

#### Scenario: Minuta con múltiples hablantes
- **GIVEN** un audio con al menos dos voces distintas
- **WHEN** el pipeline completa la etapa `minuta`
- **THEN** el pipeline termina sin error y `minutes.json` contiene exactamente las secciones solicitadas; si `resumen` fue una de ellas, su valor no está vacío

#### Scenario: Minuta con un único hablante
- **GIVEN** un audio con una sola voz
- **WHEN** el pipeline completa la etapa `minuta`
- **THEN** el pipeline termina sin error y `minutes.json` contiene exactamente las secciones solicitadas; si `resumen` fue una de ellas, su valor no está vacío

#### Scenario: Hablantes sin nombre asignado o con nombres repetidos
- **GIVEN** un pipeline en la etapa `asociar` con dos o más hablantes detectados, sin identificación de nombre o con nombres idénticos entre hablantes
- **WHEN** se completa la etapa `asociar`
- **THEN** `transcription.json` contiene los segmentos con `"name": null` para los hablantes no identificados o con el nombre asignado aunque sea repetido, sin omitir segmentos ni lanzar error

#### Scenario: Secciones no seleccionadas o vacías
- **GIVEN** una solicitud de minuta con solo un subconjunto de secciones habilitadas (p.ej. únicamente `resumen`)
- **WHEN** el pipeline completa la etapa `minuta`
- **THEN** `minutes.json` contiene únicamente las secciones solicitadas y no hay error por secciones ausentes; el campo `resumen` no está vacío

### Requirement: Persistencia de archivos de salida
Los archivos de salida del pipeline SHALL permanecer íntegros y legibles después de que el proceso termine, incluyendo tras un reinicio del sistema operativo.

#### Scenario: Archivos accesibles después del proceso
- **GIVEN** un pipeline que completó exitosamente
- **WHEN** se cierra la aplicación y se vuelve a abrir
- **THEN** los archivos del directorio de salida son legibles, el JSON es válido y `workflow.json` mantiene estado `completado`

#### Scenario: Reanudación sin reprocesamiento
- **GIVEN** un directorio de salida con un pipeline previamente completado
- **WHEN** se intenta procesar el mismo archivo nuevamente
- **THEN** el sistema detecta que ya existe un resultado vigente y no reprocesa las etapas completadas

### Requirement: Formato de entrada aceptado
El sistema SHALL aceptar archivos de audio en los formatos soportados por ffmpeg y convertirlos internamente a WAV 16 kHz mono PCM 16 sin intervención del usuario.

#### Scenario: Archivo MP3 como entrada
- **GIVEN** un archivo MP3 de audio de reunión
- **WHEN** se selecciona como fuente de entrada
- **THEN** el pipeline lo ingesta correctamente y produce `audio.wav` en el formato canónico

#### Scenario: Archivo WAV con frecuencia distinta
- **GIVEN** un archivo WAV a 44.1 kHz o 48 kHz
- **WHEN** se selecciona como fuente de entrada
- **THEN** el pipeline lo remuestrea y produce `audio.wav` a 16 kHz mono PCM 16
