# Proposal

## Why

La Etapa 4 del pipeline (asociación y etiquetado de hablantes, responsable Matías) está definida en [`hito-3/pipeline-etapas-y-herramientas.md`](../../../../../hito-3/pipeline-etapas-y-herramientas.md) y no tiene implementación. Sin ella, `diarization.json` (Etapa 2) y `asr.json` (Etapa 3) no se unen, no existe `transcription.json` y la minuta (Etapa 5) no tiene entrada ni responsables por nombre. El happy path de 2.1 exige que el usuario vea una ficha por hablante y escriba su nombre; el plan 4.1 asigna esta pieza a la semana 8.

## What Changes

| Pieza | Qué hace |
|---|---|
| Validación de entradas | `audio.wav`, `diarization.json` y `asr.json` se validan contra sus contratos antes de procesar (criterio general 6) |
| Asociación | Cada palabra de `asr.json` se asigna a un hablante de `diarization.json`; las palabras seguidas del mismo hablante forman una intervención |
| Marcas de confianza | `overlap` y `ambiguous` por intervención (2.2, punto 2) |
| Fragmento por hablante | Tramo de 5 a 15 s en que habla solo, con su texto, y los tramos siguientes para «Otro fragmento» |
| Fichas de etiquetado | Ventana PySide6, una ficha por hablante ordenada por tiempo de habla: reproducir, otro fragmento, nombre (2.2, punto 5) |
| Mismo nombre en dos etiquetas | Se tratan como una persona (2.1.2) |
| API en dos pasos | Paso 1: asociar y devolver los datos de las fichas. Paso 2: recibir los nombres y escribir `speakers.json` y `transcription.json`. El orquestador decide cómo pausar entre ambos |
| Modo sin interfaz | CLI: `name: null` y sin `speakers.json` |
| Panel de procesamiento | `PoC/paso1_captura/panel_procesamiento.py`: abre las fichas y usa los nombres del contrato (`minutes.md`, `transcription.json`) |

**Fuera de alcance:** el orquestador `procesar.py` y su protocolo (Bruno), el script de contratos de 2.3, la muestra congelada y la reunión de prueba (entregables de la semana 7, cambio aparte), un `transcription.md` legible, la edición de transcripciones o turnos (2.2, punto 3) y los cambios en las Etapas 2, 3 y 5.

## Capabilities

### New Capabilities
- `asociacion-hablantes`: validación de las tres entradas, asociación palabra → hablante, intervenciones, marcas de confianza, `transcription.json` y modo sin interfaz.
- `etiquetado-hablantes`: fragmentos por hablante, fichas de etiquetado, unificación por nombre, `speakers.json` e integración con el panel de procesamiento.

### Modified Capabilities
<!-- Ninguna: no hay specs existentes en openspec/specs/. -->

## Impact

| Qué | Detalle |
|---|---|
| Código nuevo | `PoC/paso4_asociacion/` (provisorio hasta que el equipo unifique `PoC/pasoN_*` y `src/*`) |
| Código modificado | `PoC/paso1_captura/panel_procesamiento.py` · `.gitignore` (excepción `!PoC/paso4_asociacion/`) |
| Dependencias | Ninguna nueva: soundfile, NumPy, sounddevice y PySide6 ya están en el `.venv` de la interfaz (Python 3.14). La asociación usa solo la biblioteca estándar, para correr también en el entorno 3.12 del orquestador. Sin GPU |
| Bruno (Etapa 5 y orquestación) | Acordar cómo se pausa el pipeline y cómo se llama a la API en dos pasos. `transcription.json` respeta lo que lee `src/minutas/entrada.py` |
| Luisa (Etapa 2) | Tarea 7.5 de su `tasks.md`: comprobar que la Etapa 4 consume `diarization.json` sin transformaciones |
| Felipe (Etapa 3) | `asr.json` puede traer segmentos con `words: []` y fines hasta 1 s después del audio; la Etapa 4 los acepta |
