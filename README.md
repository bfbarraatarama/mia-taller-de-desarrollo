# Taller de desarrollo — MIA

El trabajo y los entregables del **Hito 2** se encuentran en [hito-2/README.md](hito-2/README.md). Allí están el mapa de fuentes, el EDA reproducible, el datasheet, el veredicto y las instrucciones completas de ejecución y verificación.

La definición de la prueba de concepto del **Hito 3** está en [hito-3/definicion-de-la-poc.md](hito-3/definicion-de-la-poc.md). Como material de apoyo, el plan de evaluación de herramientas por módulo está en [hito-3/plan_evaluacion_workflow_minutas.md](hito-3/plan_evaluacion_workflow_minutas.md).

## Aplicación integrada

La aplicación comparte **un único núcleo Python** (`src.pipeline`) entre interfaz PySide6,
notebooks, evaluación y una entrada de terminal mínima. Las implementaciones originales
se conservaron al migrar captura a `src/captura`, diarización a `src/diarizacion`,
Whisper a `src/stt`, asociación a `src/asociacion` y minutas a `src/minutas`.
Los contenidos históricos del Hito 2 y los documentos de diseño continúan separados.

### Organización del repositorio

- `src/`: implementación integrada, con los README de cada etapa.
- `tests/`: pruebas automatizadas de las etapas e integración.
- `evaluacion/`: herramientas y evidencias reproducibles por componente (diarización, asociación y STT). Ejecutar los módulos desde la raíz.
- `docs/`: notas técnicas y especificaciones OpenSpec originales. Sus registros históricos no se reescriben.
- `notebooks/`: clientes y análisis del flujo actual; `notebooks/historicos/` conserva evidencia de contratos anteriores.
- `hito-2/` y `hito-3/`: entregables académicos; los scripts, datos y pruebas del Hito 2 se mantienen juntos para reproducir ese entregable.

Los resultados de reuniones se guardan en `resultados/` (local). Los datos derivados y reportes de trabajo de diarización se guardan en `evaluacion/diarizacion/datos/` y `evaluacion/diarizacion/reportes/` (locales); `evaluacion/diarizacion/resultados/` contiene los resultados publicados versionados. El ejemplo de asociación escribe en `evaluacion/asociacion/ejemplo_ideal/generado/` y el de STT en `evaluacion/stt/generado/` (ambos locales).
Para una copia anterior, las carpetas locales de `PoC/` no se borran automáticamente: copiar, sin sobrescribir, grabaciones a `resultados/grabaciones/` y los datos preparados a `evaluacion/diarizacion/datos/` si se necesitan. Los resultados locales de STT de `data/ASR/tmp/test_asr/` pueden copiarse a `evaluacion/stt/generado/`. No mover originales utilizados en reuniones previas sin revisar las rutas de sus manifiestos. No versionar archivos con audios ni datos privados. Los reportes antiguos conservan sus rutas originales y son evidencia histórica; las ejecuciones nuevas registran rutas relativas al directorio de evaluación.

### Entorno único para todo el repositorio

Python 3.12 y un solo `.venv` en la raíz. La instalación incluye la PoC, las
pruebas, las evaluaciones, los notebooks y la adquisición y procesamiento de datos.
`pyproject.toml` declara las dependencias directas, `constraints.txt` fija las
versiones conocidas y `requirements.txt` reúne la instalación completa. Elegir
un único perfil (`requirements-cpu.txt` o `requirements-cu128.txt`), según el equipo.
No hay requisitos de instalación por etapa; no crear entornos adicionales ni utilizar `uv`.

#### Ubuntu 24.04 (escritorio con PipeWire)

Desde la raíz del repositorio. Habilitar los repositorios Universe y Multiverse
si no están disponibles (el complemento RAR de 7-Zip está en Multiverse).

```bash
sudo apt install --no-remove python3.12 python3.12-venv ffmpeg libportaudio2 \
    pulseaudio-utils pipewire-bin pipewire-jack espeak-ng 7zip 7zip-rar \
    libarchive13t64 libxcb-cursor0

test -d .venv || python3.12 -m venv .venv
.venv/bin/python --version
```

Elegir **uno** de estos comandos (CUDA 12.8 requiere NVIDIA y un controlador compatible):

```bash
.venv/bin/python -m pip install -r requirements-cpu.txt
```

```bash
.venv/bin/python -m pip install -r requirements-cu128.txt
```

`ffmpeg` y `ffprobe` procesan audio; TorchCodec 0.7 requiere FFmpeg compartido
4 a 7 (Ubuntu 24.04 incluye 6.1). PortAudio y PipeWire/JACK permiten la captura y
reproducción. eSpeak NG genera el ejemplo sintético de asociación; 7-Zip con RAR y
libarchive permiten verificar y preparar los datos de evaluación y del Hito 2.
No reemplazar una instalación de audio operativa por otro servidor de sonido.

`pw-jack` expone JACK al proceso sin cambiar la configuración global. La captura
automática necesita una sesión PipeWire activa y fuentes disponibles; no basta
con instalar las bibliotecas.

#### Windows 11 (PowerShell)

Instalar Python 3.12 de 64 bits, [7-Zip](https://www.7-zip.org/) y
[eSpeak NG](https://github.com/espeak-ng/espeak-ng/releases), con sus ejecutables
accesibles en PATH (7-Zip también admite `SIETE_ZIP` o su ubicación estándar).
Preparar FFmpeg compartido 7.1.1 y registrar sus DLL según el
[procedimiento de diarización](src/diarizacion/README.md#4-ffmpeg-711-shared-sin-modificar-el-path-del-sistema),
además de exponer `ffmpeg` y `ffprobe` al PATH de la sesión. Para libarchive,
instalar [MSYS2](https://www.msys2.org/) y, desde su terminal UCRT64, ejecutar
`pacman -S mingw-w64-ucrt-x86_64-libarchive`. En PowerShell, si MSYS2 se instaló
en `C:\msys64`, agregar `$env:Path += ";C:\msys64\ucrt64\bin"` para esa sesión.
El cargador reconoce `archive`, `libarchive` y `libarchive-13` en Windows;
`src.verificar_entorno` comprueba que la biblioteca pueda cargarse.
La instalación nativa de libarchive y la reproducción completa del Hito 2 en
Windows todavía requieren validación. La captura utiliza fuentes manuales de
micrófono y loopback; configurar un dispositivo de retorno de audio del sistema.

```powershell
if (-not (Test-Path .venv)) { py -3.12 -m venv .venv }
.venv\Scripts\python.exe --version
```

Elegir **uno** de estos comandos:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-cpu.txt
```

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-cu128.txt
```

Completar el procedimiento de DLL de FFmpeg después de crear el entorno y antes de verificarlo.

El entorno integrado se basa en las versiones verificadas en Linux CUDA; las
restricciones no constituyen un lock multiplataforma exhaustivo ni una garantía
de instalación limpia en Windows. Los wheels de PyTorch fijan sus dependencias
específicas de plataforma; el verificador informa distribuciones adicionales.

#### Modelos, credenciales y datos

- Instalar [Ollama](https://ollama.com/download), iniciar el servicio local y ejecutar
  `ollama pull qwen2.5:7b`. Comprobar el modelo con `ollama list` en el servidor local.
- Aceptar las condiciones de `pyannote/speaker-diarization-community-1` en Hugging Face
  y completar `HF_TOKEN` en una copia local de `.env.example` llamada `.env` (no
  sobrescribir una configuración existente). Pyannote y Whisper descargan sus pesos
  al primer uso cuando no están en caché.
- Para los experimentos autorizados con Bedrock, seguir
  [la configuración de la Etapa 5](src/minutas/README.md); no versionar credenciales.
- Para reproducir el EDA y las evaluaciones con datos reales, seguir las instrucciones
  de [Hito 2](hito-2/README.md) y [diarización](src/diarizacion/README.md). Los originales
  restringidos y las autorizaciones individuales no se obtienen por instalar paquetes.
- Abrir notebooks desde el entorno raíz mediante `.venv/bin/python -m jupyter lab`
  (Windows: `.venv\Scripts\python.exe -m jupyter lab`). Usar el kernel de ese entorno.

#### Verificación y ejecución

Después de instalar los paquetes y preparar las herramientas de sistema y los modelos:

```bash
# Linux (agregar --gpu al verificador si se eligió cu128):
pw-jack .venv/bin/python -m src.verificar_entorno
pw-jack .venv/bin/python -m src.interfaz
```

```powershell
# Windows (agregar --gpu al verificador si se eligió cu128):
.venv\Scripts\python.exe -m src.verificar_entorno
.venv\Scripts\python.exe -m src.interfaz
```

El verificador comprueba versiones, `pip check`, importaciones, bibliotecas, herramientas
locales y la plataforma gráfica de Qt cuando hay sesión; no descarga modelos ni ejecuta
inferencias ni solicita credenciales remotas. No sustituye las pruebas funcionales.

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
Los resultados previos se reutilizan si son íntegros, coinciden sus parámetros
pertinentes y sus dependencias están vigentes. La consulta distingue la ejecución
activa, los checkpoints vigentes y la duración del audio. En `tiempos` se registra
la latencia activa de la solicitud y, cuando se puede medir, la espera humana;
los tiempos desconocidos se representan con `null`. Los detalles y la
fundamentación del diseño se encuentran en [Orquestación de reuniones](docs/orquestacion.md).
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
.venv/bin/python -m compileall -q src tests evaluacion hito-2/scripts
.venv/bin/python -m pytest -q -rs tests hito-2/tests
```

Las pruebas de diarización marcadas `slow`, `calidad` o `gpu` deben invocarse
expresamente con `-m` cuando se disponga de sus recursos externos (`python -m pytest tests/diarizacion -m calidad -rs`, por ejemplo). Sin los RTTM locales solo se verifican la integridad y coherencia de las evidencias publicadas; no se recalculan las métricas. Las verificaciones
reales de Qt, grabación, Whisper, pyannote, Ollama y Bedrock son adicionales a los
tests de contrato con modelos simulados.
