# validacion-funcional/flujo-principal Specification

## Purpose
Garantiza que el pipeline completo —desde un archivo de audio hasta la minuta generada— produce los artefactos correctos y los persiste en disco de forma duradera en todas las plataformas soportadas.

## Requirements

### Requirement: Pipeline completo desde archivo de audio
Dado un archivo WAV de entrada válido, el sistema SHALL ejecutar las cinco etapas del pipeline (preparar, diarizar, transcribir, asociar, minuta) en orden y producir todos los archivos de salida definidos.

#### Scenario: Ejecución exitosa en Windows/CPU
- **GIVEN** un archivo WAV de audio de una reunión (≥ 30 segundos, 16 kHz, mono, PCM 16)
- **WHEN** se inicia el procesamiento con perfil CPU desde la GUI o la CLI
- **THEN** el pipeline completa todas las etapas sin errores y el directorio de salida contiene `workflow.json` con estado `completado`, `audio.wav`, `ingesta.json`, `diarization.json`, `asr.json`, `transcripcion.json`, `minutes.json` y `minutes.md`

#### Scenario: Ejecución exitosa en Linux/GPU
- **GIVEN** un archivo WAV de audio de una reunión (≥ 30 segundos, 16 kHz, mono, PCM 16)
- **WHEN** se inicia el procesamiento con perfil GPU (CUDA) desde la GUI o la CLI
- **THEN** el pipeline completa todas las etapas sin errores y el directorio de salida contiene los mismos archivos que en Windows/CPU

#### Scenario: Ejecución exitosa en Linux/CPU
- **GIVEN** un archivo WAV de audio de una reunión (≥ 30 segundos, 16 kHz, mono, PCM 16)
- **WHEN** se inicia el procesamiento con perfil CPU desde la GUI o la CLI en Linux
- **THEN** el pipeline completa todas las etapas sin errores y el directorio de salida contiene los mismos archivos que en Windows/CPU

### Requirement: Contenido mínimo de la minuta generada
El archivo `minutes.md` SHALL contener al menos un bloque de texto con participantes identificados y el archivo `minutes.json` SHALL contener una estructura con resumen y secciones no vacías.

#### Scenario: Minuta con múltiples hablantes
- **GIVEN** un audio con al menos dos voces distintas
- **WHEN** el pipeline completa la etapa `minuta`
- **THEN** `minutes.md` contiene al menos dos nombres de hablantes diferentes y `minutes.json` tiene un campo `resumen` no vacío

#### Scenario: Minuta con un único hablante
- **GIVEN** un audio con una sola voz
- **WHEN** el pipeline completa la etapa `minuta`
- **THEN** `minutes.md` contiene texto de transcripción y `minutes.json` tiene un campo `resumen` no vacío

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
