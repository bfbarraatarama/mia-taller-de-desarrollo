# Proposal

## Why

La Etapa 2 del pipeline (diarización, responsable Luisa) está definida en [`hito-3/pipeline-etapas-y-herramientas.md`](../../../hito-3/pipeline-etapas-y-herramientas.md) pero no tiene implementación. Sin `diarization.json`, la Etapa 4 no puede atribuir intervenciones y la minuta no puede asignar responsables. Además, la responsable desarrolla en una máquina Windows sin GPU, mientras que la PoC se ejecuta en las RTX 3050 de 6 GB del equipo. Por eso el mismo código tiene que poder desarrollarse y probarse en CPU y correr sin cambios en GPU.

## What Changes

- Nuevo módulo independiente de diarización en `PoC/paso2_diarizacion/`, con el modelo `pyannote/speaker-diarization-community-1`. Recibe el `audio.wav` normalizado de la Etapa 1 (16 kHz, mono, PCM16) y escribe `diarization.json`. Se puede ejecutar solo desde la línea de comandos, para desarrollo y pruebas, y el orquestador lo puede invocar después como función.
- El audio lo lee pyannote con **FFmpeg**, como fija el documento del pipeline. No se incorpora `soundfile`. FFmpeg es una dependencia del sistema que comparten las etapas 1 a 3. Tiene que ser una build con bibliotecas compartidas, de la serie 4 a 7, que es lo que acepta `torchcodec 0.7`; la versión verificada es la 7.1.1 *shared*. En Windows se registra solo para el venv de la etapa, sin modificar el `PATH` del sistema. Se documenta cómo instalarla y verificarla. La validación del formato del WAV lee solo su cabecera, con la biblioteca estándar.
- `diarization.json` respeta **exactamente** el contrato publicado (`{"segments": [{"start", "end", "speaker"}]}`). Se conservan los solapamientos y no se agregan campos.
- Los segmentos se normalizan antes de escribirse: redondeo a 3 decimales y **recorte a los límites del WAV** de todo segmento con alguna parte dentro del audio, sea cual sea su exceso. Solo se descartan los segmentos fuera del audio o vacíos tras redondear, y al final se valida otra vez el contrato. Los segmentos corregidos y descartados y el mayor exceso recortado (`exceso_fin_max_s`) se registran en los metadatos.
  - Esta regla reemplaza a la original, que descartaba todo exceso mayor a 0,05 s.
  - El cambio se hizo el 08/11/2026: en una grabación interrumpida, la regla original hizo perder 6 s de habla real.
  - `tolerancia_fin_s` se conserva en el meta como campo heredado, sin efecto en los descartes.
- Nuevo archivo `diarization.meta.json` con los metadatos técnicos de **una ejecución exitosa**, vinculado a su `diarization.json` para poder comprobar que ambos corresponden a la misma ejecución.
- Ante un fallo, el error se registra en un archivo aparte, `diarization.error.json`. El último `diarization.json` válido y sus metadatos no se tocan, y el fracaso se informa con el código de salida y con una excepción. Cada reunión tiene su propia carpeta de resultados.
- Cantidad de hablantes: por defecto la estima pyannote. Se puede indicar la cantidad exacta con `num_speakers`, que es opcional y no altera el contrato.
- Selección de dispositivo automática, con CUDA si está disponible y CPU si no, y opción de elegirlo de forma explícita. Pedir CUDA sin GPU es un error claro. En GPU, la memoria del modelo se libera al terminar.
- Token de Hugging Face personal de cada integrante, desde el entorno o desde `.env`, sin credenciales en el repositorio.
- Validador del contrato, reutilizable por el script de contratos de 2.3 y por la Etapa 4.
- **Dataset de test de UBA Games (Figshare v2):** un script nuevo y reproducible, `PoC/paso2_diarizacion/evaluacion/preparar_figshare.py`, prepara la sesión **S26**, empezando por una sola grabación (`s26.objects.04`, de 52,3 s) y ampliándola después al resto de S26. Toma los archivos ya extraídos en `hito-2/.cache/uba_games/figshare-v2/extraidos/`, verificados contra el listado de los RAR. La entrada del modelo es el **WAV estéreo completo** de cada tarea convertido a mono, como hace la aplicación; los WAV separados por canal no se usan como entrada. La comparación con S21–S23 queda para más adelante. Para cada grabación:
  - verifica los RAR originales contra `fuentes.toml` y `fuentes.lock.json`, y cada archivo extraído contra su entrada del RAR (tamaño y CRC32), con el listado de 7-Zip y sin extraer nada;
  - aplica los criterios de validez y la tolerancia de 0,01 s del Hito 2;
  - convierte el WAV estéreo a mono de 16 kHz con la fórmula del Hito 2, `(izquierda + derecha) // 2`, sin modificar el original;
  - genera la referencia de dos hablantes a partir de las anotaciones de los dos canales, con una política explícita para `#`, las etiquetas especiales, los solapamientos y las tolerancias, y la valida antes de calcular las métricas;
  - calcula un **indicador de cobertura** de la anotación (energía contra intervalos anotados) como indicio de una transcripción incompleta, sin cambiar la referencia.

  Un manifiesto versionado registra la procedencia, la selección de grabaciones (válidas y excluidas con su motivo), los CRC32 y los SHA-256. No se modifican los originales ni `hito-2/scripts/armar_muestra.py`.
- Pruebas en tres niveles:
  1. Unitarias, sin el modelo real. Incluyen la preparación del dataset con archivos sintéticos.
  2. Integración entre la Etapa 1 y la Etapa 2 en CPU, en la máquina Windows sin GPU, con WAV reales de 30 a 60 s grabados con la interfaz de la Etapa 1. Comprueba el contrato de salida de la Etapa 1, que la Etapa 2 lo recibe y lo procesa, que el `diarization.json` tiene intervalos y etiquetas de hablante válidas, y que los archivos de la Etapa 1 quedan intactos.
  3. Evaluación de calidad sobre el dataset de test, **en CPU o en GPU**.
     - Valida el contrato al 100 %.
     - Cuando la referencia es utilizable, calcula sin umbral, por grabación, por sesión y en total: **DER estricto** (`collar=0.0`), **DER con tolerancia** (criterio NIST de ±0,25 s por borde, `collar=0.5` en pyannote) y **JER**, todos con habla superpuesta. También sus componentes (falsa alarma, habla perdida y confusión) y la dispersión entre grabaciones (mediana, cuartiles y peor grabación).
     - Registra la **cantidad de hablantes** detectada contra la de la referencia. Una **corrida diagnóstica con `num_speakers=2`** separa el error de estimar la cantidad del de segmentar.
     - El reporte declara las limitaciones de la referencia: frases transcritas por canal, sin acuerdo entre anotadores, 2 hablantes y dominio de juego.
     - Las pruebas propias de CUDA (memoria y compatibilidad CPU/GPU) quedan aparte, para un integrante con GPU.
  - El nivel 2 (grabaciones propias con una secuencia conocida) es validación técnica más verificación básica, no evaluación de calidad.
- Tolerancia terminal de 0,01 s del Hito 2: los fines de anotación que se pasan del audio dentro de ese margen se ajustan a la duración real para la evaluación, y los tiempos originales quedan en el manifiesto de procedencia.

Fuera de alcance: el orquestador `PoC/paso2_procesamiento/procesar.py` y su protocolo `--jsonl`, la transcripción (Etapa 3), la asociación (Etapa 4), la minuta (Etapa 5), la corrección del eco del paso 1, los umbrales de DER y JER, las otras seis sesiones de Figshare, CALLHOME y cualquier cambio en los scripts del Hito 2.

## Capabilities

### New Capabilities
- `diarizacion-hablantes`: diarización de un audio normalizado en segmentos por hablante con el contrato de `diarization.json`. Cubre la normalización de segmentos, los metadatos de la ejecución exitosa, el registro separado de errores sin perder el último resultado válido, la selección de dispositivo CPU/GPU, la liberación de la GPU y el token personal.
- `evaluacion-diarizacion`: preparación reproducible del dataset de test (S26 de UBA Games, empezando por `s26.objects.04`), construcción y validación de las referencias de dos hablantes, indicador de cobertura de la anotación, y cálculo y registro del DER y el JER contra ellas.

### Modified Capabilities
<!-- Ninguna: no hay specs existentes en openspec/specs/. -->

## Impact

- **Código nuevo:** `PoC/paso2_diarizacion/` (módulo, validador de contrato, script de preparación del dataset, pruebas, `requirements.txt` y `README.md`). No se modifican el paso 1, los documentos del Hito 3 ni los scripts del Hito 2.
- **`.gitignore`:** hoy ignora `PoC/*` salvo `paso1_captura/`. Hay que agregar la excepción `!PoC/paso2_diarizacion/` y seguir excluyendo sus datos derivados y reportes.
- **Dependencias:**
  - Paquetes: PyTorch 2.8.0 + torchaudio (wheel CPU o cu128), `pyannote.audio>=4.0` y `python-dotenv`. Para las pruebas y el DER, `pytest` y `pyannote.metrics`. Python 3.12. No se usa `soundfile`.
  - Herramientas del sistema: FFmpeg 7.1.1 *shared*, que comparten las etapas 1 a 3 (`torchcodec 0.7` acepta de la 4 a la 7), y 7-Zip para la preparación del dataset.
  - Versiones exactas: `requirements.txt` fija las dependencias directas, `constraints.txt` fija todo el árbol verificado y `verificar_entorno.py` comprueba el entorno.
- **Entorno compartido:** el entorno de las etapas 2 y 3 es común con Felipe (Etapa 3), así que la variante de PyTorch se coordina con él. La GPU de referencia de 6 GB se usa en secuencia con Whisper: la diarización tiene que dejarla liberada.
- **Orquestador (futuro):** tiene que decidir por el código de salida o por la excepción, y no por la presencia de `diarization.json`. Detener el flujo y ofrecer un nuevo intento le corresponde a él.
- **Etapa 4 (Matías):** consume `diarization.json` sin cambios y puede reutilizar el validador.
- **Datos:** la preparación usa los archivos ya extraídos en `hito-2/.cache/uba_games/figshare-v2/extraidos/`, verificados contra `phrases.rar` y `wavs.rar` de la misma caché. Ninguno está en git. No se descarga nada. Si en otra máquina faltan los RAR, se obtienen con `hito-2/scripts/descargar_fuentes.py`. Ni la preparación ni la evaluación de calidad necesitan GPU: solo las pruebas propias de CUDA.
