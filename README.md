# Taller de desarrollo — MIA

El trabajo y los entregables del **Hito 2** se encuentran en [hito-2/README.md](hito-2/README.md). Allí están el mapa de fuentes, el EDA reproducible, el datasheet, el veredicto y las instrucciones completas de ejecución y verificación.

La definición de la prueba de concepto del **Hito 3** está en [hito-3/definicion-de-la-poc.md](hito-3/definicion-de-la-poc.md). Como material de apoyo, el plan de evaluación de herramientas por módulo está en [hito-3/plan_evaluacion_workflow_minutas.md](hito-3/plan_evaluacion_workflow_minutas.md).

## Integración de la PoC (rama `feature/integracion-poc`)

La aplicación comparte **un único núcleo Python** (`src.pipeline`) entre interfaz PySide6,
notebooks, evaluación y una entrada de terminal mínima. Las implementaciones originales
se conservaron al migrar captura a `src/captura`, diarización a `src/diarizacion`,
Whisper a `src/stt`, asociación a `src/asociacion` y minutas a `src/minutas`.
Los contenidos históricos del Hito 2 y los documentos de diseño continúan separados.

### Entorno único

Se requiere **Python 3.12**, FFmpeg en `PATH` (con bibliotecas compartidas disponibles
para TorchCodec) y, para la diarización real, acceso aceptado al modelo
`pyannote/speaker-diarization-community-1` en Hugging Face. La variante CUDA debe
ser compatible con el controlador instalado. No se usa `uv`.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
# Elegir SOLO una variante de PyTorch 2.8 y TorchAudio 2.8:
.venv/bin/python -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
# Para CUDA 12.8, sustituir el índice anterior por https://download.pytorch.org/whl/cu128
.venv/bin/python -m pip install -e '.[test]' -c src/diarizacion/constraints.txt
.venv/bin/python -m pip check
.venv/bin/python -m src.diarizacion.verificar_entorno
.venv/bin/python -m src.interfaz
```

En Windows crear con `py -3.12 -m venv .venv` y utilizar `.venv\Scripts\python.exe`
en lugar de `.venv/bin/python`. Para la salida Qt en un escritorio Linux se necesita
un servidor gráfico, dispositivo de audio y bibliotecas de PortAudio. El grabador
mezcla micrófono y sistema en una pista; la integración no crea un sistema multitrack.

### Ejecución programática

```python
from pathlib import Path
from src.pipeline import SolicitudReunion, procesar_reunion, consultar_reunion
from src.minutas.generacion import ConfiguracionMinutas

solicitud = SolicitudReunion(
    fuentes=(Path('/ruta/primer_corte.wav'), Path('/ruta/segundo_corte.wav')),
    salida=Path('resultados/reunion_ejemplo'),
    minutas=ConfiguracionMinutas(modelo='qwen2.5-7b', secciones=('resumen', 'temas', 'acciones')),
)
resultado = procesar_reunion(solicitud)  # API sin Qt, identifica hablantes con etiquetas
print(resultado['estado'], resultado['artefactos'])
```

La API ofrece también `preparar_reunion`, `continuar_reunion`, `consultar_reunion`,
`reetiquetar_reunion` y `cancelar_reunion`. En modalidad GUI, el trabajador detiene
la inferencia antes de las fichas de hablantes. La identificación admite nombres
repetidos o vacíos y puede modificarse sin repetir diarización ni STT válidos.

**CLI mínima de la PoC:**

```bash
.venv/bin/python -m src.pipeline ejecutar primer_corte.wav segundo_corte.wav \
    --salida resultados/reunion_ejemplo --modelo qwen2.5-7b \
    --secciones resumen,temas,acciones
.venv/bin/python -m src.pipeline estado --reunion resultados/reunion_ejemplo
```

La CLI corresponde a la modalidad no gráfica de la especificación del Hito 3;
**no** se deriva de la consigna del pipeline de datos de la Clase 7. El notebook
`notebooks/workflow_poc.ipynb` es cliente de la misma API, nunca un segundo pipeline.

### Persistencia, privacidad y límites de validación

Por omisión, cada conjunto ordenado de fuentes se guarda en una subcarpeta
determinista de `resultados/`: volver a procesar las mismas fuentes no crea
carpetas adicionales, y dos reuniones diferentes no se sobrescriben.
Una ruta de reunión explícita por API o GUI tiene precedencia.
Cada reunión mantiene un solo `workflow.json` sobrescrito al
cambiar de etapa, `ingesta.json`, los originales necesarios y los artefactos
con sus nombres contractuales. Los eventos de progreso son transitorios.
Los resultados previos solo se reutilizan si coinciden sus hashes y parámetros.
Las salidas están excluidas de Git. El mecanismo de publicación por archivo no
promete transacciones atómicas de varios archivos ante un corte eléctrico.

Todos los modelos de minutas **son experimentales**; no representan necesariamente
la elección de modelos de un producto final. Los proveedores remotos permiten
experimentar con capacidades que no caben en el hardware de la PoC, sin afirmar
ninguna equivalencia con su eventual ejecución local. Los destinos externos
(AWS Bedrock o `OLLAMA_HOST` no local) exigen autorización explícita por solicitud;
se envía la transcripción y el prompt, **no el WAV** desde minutas. El uso
remoto no redefine la motivación de confidencialidad del producto.

Los tests sin GPU comprueban contratos y conexiones; **no demuestran** calidad de
minutas, compatibilidad de VRAM de 6 GB o cumplimiento de los umbrales de Hito 3 §2.3.
Esas evidencias requieren las muestras y el hardware correspondientes. Los modelos
reales, credenciales, WAV personales y cachés no deben versionarse.

### Pruebas

```bash
.venv/bin/python -m compileall -q src
.venv/bin/python -m pytest -q PoC/paso2_diarizacion/tests
.venv/bin/python -m pytest -q PoC/paso4_asociacion/tests
.venv/bin/python -m pytest -q src/minutas/tests src/stt/test_asr_core.py
.venv/bin/python -m pytest -q tests/integracion
```

Las pruebas de diarización marcadas `slow`, `calidad` o `gpu` deben invocarse
expresamente con `-m` cuando se disponga de sus recursos externos. Las verificaciones
reales de Qt, grabación, Whisper, pyannote, Ollama y Bedrock son adicionales a los
tests de contrato con modelos simulados.
