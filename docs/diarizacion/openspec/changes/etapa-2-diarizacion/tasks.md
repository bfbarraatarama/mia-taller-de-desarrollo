# Tasks

> **Dónde se ejecuta cada grupo.** Los grupos 1 a 6 se hacen y se verifican en la máquina de desarrollo (Windows, sin GPU). El grupo 7 se prepara en esa máquina, pero sus pruebas de GPU se verifican en un equipo con GPU NVIDIA.
>
> **Hasta el 09/11/2026:**
> - la evaluación de calidad en GPU la hizo una compañera en una RTX 4060 Ti (tarea 7.7, informada, sin archivos versionados);
> - las RTX 3050 de referencia todavía no se verificaron.

## 1. Estructura y entorno

- [x] 1.1 Crear `PoC/paso2_diarizacion/` con los módulos de la sección 1 del diseño, `evaluacion/`, `tests/`, `requirements.txt` y `README.md`. Agregar a `.gitignore` `!PoC/paso2_diarizacion/`, `PoC/paso2_diarizacion/datos/` y `PoC/paso2_diarizacion/tests/reportes/`. Verificar con `git check-ignore -v` que `diarizar.py` **no** está ignorado y que `datos/x.wav` y `tests/reportes/x.json` sí
- [x] 1.2 Escribir `requirements.txt` sin `torch`/`torchaudio` ni `soundfile` (`pyannote.audio>=4.0`, `python-dotenv`, `pytest`, `pyannote.metrics`), crear el entorno 3.12 e instalar primero el wheel CPU de `torch==2.8.0` y después el `requirements.txt`; verificar que `import torch, pyannote.audio, numpy, pandas` funciona y que `torch.__version__` da `2.8.0+cpu` con `cuda.is_available()` en `False`
- [x] 1.3 Instalar FFmpeg 7.1.1 *shared* como dependencia del sistema, compatible con `torchcodec 0.7` (versiones 4 a 7), sin modificar el `PATH` del sistema. En Windows: carpeta local en `%LOCALAPPDATA%\ffmpeg7\` y `ffmpeg_dll_dir.pth` en el venv con `os.add_dll_directory` (§2 y §8 del diseño). Verificar que `torchcodec` decodifica un WAV real completo dentro del entorno (muestras iguales a la cabecera) y que `import pyannote.audio` no avisa por FFmpeg. Si falla, registrar el síntoma y consultarlo con el equipo antes de considerar `soundfile`. *Hecho el 07/11/2026: la FFmpeg 9.0.2 del sistema no servía y se instaló la 7.1.1 local. Se verificó con un WAV de `C:\Windows\Media` normalizado a 16 kHz mono PCM16; el WAV de la interfaz se comprueba en el grupo 5.*
- [x] 1.4 Instalar 7-Zip en Windows y verificar que `7z i` responde desde `PATH` o desde `%ProgramFiles%\7-Zip\7z.exe`, y que lista un RAR de prueba con `7z l -slt -ba`
- [x] 1.5 Crear `tests/conftest.py`, que registra los markers `slow` y `gpu` y saltea con un motivo legible cuando faltan `HF_TOKEN`, `DIARIZACION_AUDIOS_CPU`, el dataset preparado, FFmpeg, 7-Zip o CUDA; verificar que `pytest PoC/paso2_diarizacion -m "slow or gpu" -rs` termina sin errores y lista los motivos

## 2. Contrato y normalización de segmentos

- [x] 2.1 Implementar en `contrato.py` (solo stdlib) `validar_diarizacion(datos, duracion)`, que informa cada violación con su ubicación; verificar con `tests/test_contrato.py`, que cubre un archivo válido con solapamiento y uno con tres violaciones a la vez
- [x] 2.2 Implementar `validar_par(json_path, meta_path)` y el uso por línea de comandos `python contrato.py diarization.json AUDIO [--meta ...]`, con código distinto de 0 si hay violaciones; verificar con tests de un par consistente y uno de ejecuciones distintas, y documentar el uso en el README
- [x] 2.3 Implementar `segmentos.normalizar(turnos, duracion)` según la sección 4 del diseño (`TOLERANCIA_FIN_S = 0.05`): decisión con tiempos crudos, techo `D3 <= D`, redondeo acotado a `[0, D3]` sin `-0.0` y descarte de `start >= end`, con la función de acotado reutilizable desde `evaluacion/`. Verificar con `tests/test_segmentos.py`, que cubre los casos límite de la sección 4: `D = 197531/16000` con `end == D` y con `end = D + 0.0004`; un inicio que se redondea más allá del final; excesos de 0,05 y de 0,0501 s; `start = -0.0004`; un segmento de 0,0004 s; un audio de menos de 1 ms con salida `segments: []`; desorden y dos hablantes superpuestos. Agregar una prueba de propiedad con miles de segmentos y duraciones aleatorias en cuadros de 16 kHz, con semilla fija, que comprueba que todo segmento escrito cumple `0 <= start < end <= D` y pasa `validar_diarizacion`

- [x] 2.4 Corregir la regla de normalización según el requisito "Normalización de segmentos" y el design §4 (actualizados el 08/11/2026, después de la grabación interrumpida `2026_11_08_11_41_26.wav`). La tarea 2.3 queda hecha con la regla original; esta tarea la reemplaza sin desmarcarla. Incluye:
  - **Código:**
    - `segmentos.normalizar` recorta a `[0, D3]` todo segmento con alguna parte dentro del audio, sin tolerancia, y descarta solo los que tienen `start_crudo >= D` o `end_crudo <= 0`, o quedan vacíos tras redondear;
    - devuelve además `exceso_fin_max_s`;
    - `diarizar.py` escribe en el meta `exceso_fin_max_s` y conserva `tolerancia_fin_s` (0,05) como campo heredado;
    - el contrato de `diarization.json` no cambia.
  - **Tests de regresión en `tests/test_segmentos.py`:**
    - el caso real: `D = 520000/16000 = 32,5 s` y el segmento 26,5922–32,5997 s dan `{26.592, 32.5}`, 1 corregido, 0 descartados y `exceso_fin_max_s ≈ 0,0997`;
    - los 8 turnos crudos de esa grabación (0,3685–2,3091; 2,4103–3,2878; 4,0303–8,9072; 9,3628–14,4760; 14,8641–19,0491; 19,2685–21,3947; 22,2553–24,7866; 26,5922–32,5997 s), con los 8 escritos;
    - un exceso de 0,5 s con inicio dentro del audio, recortado;
    - un inicio en −0,3 s, recortado a 0;
    - un segmento con `start >= D`, descartado;
    - la actualización de los tests de la 2.3 que esperaban un descarte por exceso (0,0501 s y −0,06 s);
    - la prueba de propiedad ampliada: ningún segmento con parte dentro del audio se pierde salvo que quede vacío;
    - un test de `diarizar` con pipeline falso que comprueba `exceso_fin_max_s` y `tolerancia_fin_s` en el meta.
  - **README:** actualizar la sección "Normalización de los tiempos" con la regla nueva y los dos campos del meta.

  Verificar que `pytest PoC/paso2_diarizacion` pasa completo, y que una nueva diarización de `2026_11_08_11_41_26.wav` escribe 8 segmentos, con el último terminando en 32,5 s, y `segmentos_descartados: 0`.

## 3. Entrada, token y dispositivo

- [x] 3.1 Implementar `entrada.validar_audio(ruta)` leyendo solo la cabecera con `wave` (existe, 16 000 Hz, 1 canal, 16 bits PCM; devuelve la duración) y la validación de `num_speakers`; verificar con `tests/test_entrada.py`, que usa WAV sintéticos escritos con `wave` en `tmp_path` (válido, inexistente, estéreo, 48 kHz, 24 bits, no WAV, `num_speakers=0`) y comprueba el mensaje
- [x] 3.2 Implementar `entrada.obtener_token()` (`HF_TOKEN`; si falta, `find_dotenv(usecwd=True)` sin sobrescribir) y el mensaje de token ausente; verificar con tests que usan `monkeypatch` y un `.env` en `tmp_path`, y que comprueban que el valor del token no aparece en ningún mensaje
- [x] 3.3 Implementar `elegir_dispositivo(modo)`; verificar con `tests/test_dispositivo.py`, que simula `torch.cuda.is_available` en `True` y `False` y cubre los cuatro escenarios de "Selección del dispositivo"

## 4. Resultados, errores y ejecución

- [x] 4.1 Implementar en `resultados.py` la carpeta de la reunión y la escritura del par (`.tmp`, `os.replace` del JSON y luego del meta con `diarization_sha256`, borrado de `diarization.error.json`); verificar con tests de dos grabaciones en la misma carpeta que dan carpetas distintas, de un par que pasa `validar_par`, de que no queda ningún `.tmp` y de que un `diarization.error.json` previo desaparece tras un éxito
- [x] 4.2 Implementar el registro del error en `diarization.error.json` sin tocar el par anterior; verificar con un test que crea un par válido, simula un fallo y comprueba que el par queda byte a byte igual y que el error registra `resultado_anterior_conservado: true` y `run_id_anterior`; y con otro test sin par previo, que comprueba que no se crea ninguno
- [x] 4.3 Implementar `diarizar(audio, salida=None, device="auto", num_speakers=None)` con imports diferidos, siguiendo la sección 3 del diseño (ruta del audio a pyannote y `out.speaker_diarization`); verificar con un pipeline falso que el par se escribe, que `num_speakers` llega al pipeline y queda en el meta, y que el contrato es igual con y sin el parámetro
- [x] 4.4 Implementar el `finally` de liberación (sección 7 del diseño) y la conversión de fallos en `DiarizacionError` con su etapa: falta de memoria en CUDA con sugerencia de `--device cpu`, y error de FFmpeg con remisión al README. Verificar con un pipeline falso que lanza `RuntimeError`, un `OutOfMemoryError` simulado y un error de decodificación, comprobando el archivo de error, el par anterior intacto, el SHA-256 del audio sin cambios y que `empty_cache` simulado se llama solo en `cuda`
- [x] 4.5 Implementar la CLI (`diarizar.py AUDIO [--salida DIR] [--device auto|cpu|cuda] [--num-speakers N]`, con códigos 0, 1 y 2) y el resumen por hablante; verificar con tests de `subprocess` sobre un audio inválido, `--device cuda` sin GPU y un fallo con resultado anterior presente (código distinto de 0), y comprobar que `--help` no importa torch
- [x] 4.6 **(Revisión del PR #8, 09/11/2026.)** Hacer consistente la publicación del par en `resultados.escribir_par`:
  - respaldar el par vigente en `.<marca>.bak` antes de publicar;
  - si falla cualquiera de los dos `os.replace`, restaurar desde el respaldo, o borrar lo publicado si no había par anterior;
  - si falla la restauración, conservar los respaldos;
  - `par_vigente()` y `run_id_vigente()` solo cuentan un par si `diarization_sha256` coincide con el SHA-256 del JSON.

  Sin cambiar el contrato de `diarization.json` ni del meta. Verificar con tests de nivel 1 que simulan fallos de `os.replace`:
  - la segunda publicación con par anterior: par byte a byte igual, `validar_par` sin violaciones, sin `.tmp` ni `.bak`;
  - la segunda publicación sin par anterior: no queda ningún archivo;
  - la primera publicación;
  - la restauración: error original con nota y `.bak` completos;
  - una ejecución posterior que no pisa esos respaldos;
  - el fallo al preparar el respaldo;
  - un par inconsistente que no cuenta como vigente;
  - un meta que no es un objeto;
  - `diarizar` con pipeline falso: etapa `escritura` y `resultado_anterior_conservado: true`.

  Correr además todo el nivel 1

## 5. Integración Etapa 1 → Etapa 2 en CPU (máquina Windows sin GPU)

> Pruebas manuales del 08/11/2026: cuatro grabaciones de la interfaz diarizadas con la CLI, registradas en [registro-pruebas.md](registro-pruebas.md).
>
> Tarea 5.2: **completada el 08/11/2026**, con una excepción y una salvedad documentadas.
> - auriculares: ✅ hecho (`2026_11_08_09_21_37.wav`, prueba 3);
> - parlantes: ✅ ejecutado y documentado (`2026_11_08_09_35_54.wav`, prueba 4), **con incidencias de captura de la Etapa 1**: pérdida de 0,124 s y deriva de 0,141 s;
> - cierre forzado: ✅ ejecutado y documentado (`2026_11_08_11_41_26.wav`, prueba 5). Reveló el defecto de normalización corregido en la tarea 2.4.
>
> Decisiones (ver "Estado de la tarea 5.2" en el registro):
> - **Excepción de una sola voz:** la prueba 5 (cierre forzado) se hizo deliberadamente con una sola voz, para validar la integridad del WAV después de un cierre inesperado.
> - **Consentimiento:** las grabaciones con dos personas presentes contaron con el consentimiento de ambas. El video público de YouTube de las pruebas 3 y 4 se acepta en el contexto académico local; no se verificó el consentimiento individual de ese hablante.
> - **`DIARIZACION_AUDIOS_CPU`** apunta a `PoC/paso1_captura/grabaciones/nivel2/`, que tiene copias de las tres grabaciones de la 5.2 con sus JSON (los originales no se tocaron). Se define en la sesión de pruebas.
>
> Verificado: 3 WAV, 2 en "completa" y 1 en "grabando"; los tres de 30 a 60 s y decodificables completos; ignorados por git; `pytest -m slow` pasa 2 de 2.
>
> Tarea 5.3: completada. `tests/test_integracion_cpu.py` pasa 6 de 6 sobre `nivel2/`, y la prueba negativa sin reporte falla por el motivo esperado.
> Tarea 5.4: completada. `tests/test_integracion_sintetica.py` pasa 8 de 8 sin el modelo (ver la sección "Tarea 5.4" del registro).
> Tarea 5.5: completada como verificación automática básica más limitaciones (reformulada el 08/11/2026). **El nivel 2 queda cerrado** como validación técnica más verificación básica; la evaluación de calidad es el nivel 3.

- [x] 5.1 Preparar el entorno del paso 1 en Windows, separado del de la Etapa 2 (`uv venv` con Python 3.14 o 3.12, e `.venv\Scripts\python.exe -m pip install -r PoC/paso1_captura/requirements.txt`), y elegir en modo manual el micrófono y una fuente de audio del sistema (Stereo Mix, loopback o VB-Cable); verificar que `captura.py --listar` muestra los dos dispositivos y que una prueba con `captura.py --duracion 10 --tono` deja un reporte con las 5 pruebas en `ok: true`
- [x] 5.2 Grabar **con la interfaz** (`interfaz.py`), con consentimiento de quienes hablan, tres grabaciones de 30 a 60 s con 2 voces: una con auriculares, otra con parlantes y una tercera cerrada a la fuerza durante la captura. Apuntar `DIARIZACION_AUDIOS_CPU` a `PoC/paso1_captura/grabaciones/` y verificar que cada WAV tiene su `.json` (las dos primeras con `estado: "completa"` y la tercera en "grabando") y que `git status` no las muestra
- [x] 5.3 Escribir `tests/test_integracion_cpu.py` (marker `slow`) con los bloques A a D de la sección 10.1 del diseño. A: cabecera con `entrada.validar_audio`, duración de 30 a 60 s, reporte con `estado: "completa"` y "salida procesable" en `ok: true` (para la interrumpida se acepta "grabando"), y **decodificación completa** de las tres grabaciones según la sección 10.1: `wave.readframes` con `nframes * 2` bytes, `torchcodec` con exactamente `nframes` muestras, y `ffmpeg -v error ... -f null -` sin salida en stderr. Si la interrumpida no se decodifica completa, el test falla antes de diarizar. B: `diarizar(..., device="cpu")` sin excepción. C: contrato al 100 %, al menos 1 etiqueta `SPEAKER_NN` y 1 segmento, meta con `cpu` y la misma duración, par consistente. D: SHA-256 del WAV y del reporte sin cambios, resultados en `grabaciones/<nombre>/` sin pisar `<nombre>.json`, y carpetas distintas por grabación. Escribir además `tests/reportes/integracion_<nombre>.json`. Verificar que `pytest PoC/paso2_diarizacion -m slow -rs` pasa con las tres grabaciones y que, si falta el reporte de una grabación, el test falla
- [x] 5.4 Agregar a los tests de nivel 1 un caso del bloque A sin modelo, con un WAV sintético y un reporte del paso 1 armados en `tmp_path` (completo, interrumpido y sin reporte), y con un WAV truncado cuya cabecera declara más cuadros de los que tiene, que la comprobación de lectura completa con `wave` tiene que rechazar. Así la lógica de compatibilidad se prueba en cualquier máquina; verificar con `pytest PoC/paso2_diarizacion -k integracion`
- [x] 5.5 Documentar en una tabla del README la **verificación automática básica** de cada grabación de `nivel2/`, a partir de `tests/reportes/integracion_*.json` y de `nivel2/<nombre>/diarization.json`:
  - hablantes esperados y detectados;
  - predominante por bloque de unos 15 s y coherencia con la secuencia diseñada;
  - reidentificación de A;
  - anomalías automáticas (segmentos de menos de 0,5 s, superposiciones, speaker no predominante y desvíos en los cambios);
  - `tiempo_s`.

  Agregar las **limitaciones** de estas grabaciones como evaluación de calidad. No hay revisión auditiva obligatoria. Reformulada el 08/11/2026: la versión original pedía una revisión manual de oído. Verificar que hay una fila por grabación, incluidas la de parlantes y la interrumpida (ver la sección "Tarea 5.5" del registro)

## 6. Preparación del dataset de test (S26, empezando por `s26.objects.04`)

> Alcance reemplazado el 08/11/2026 (antes: S21–S23). Los archivos ya están extraídos en `hito-2/.cache/uba_games/figshare-v2/extraidos/` y **no se descarga nada**. **Una tarea por vez**, con autorización.

- [x] 6.1 Implementar `evaluacion/rar7z.py`, **solo para verificar** y sin extraer:
  - localizar 7-Zip (`SIETE_ZIP`, `PATH`, `%ProgramFiles%\7-Zip\7z.exe`);
  - listar con `7z l -slt -ba` (`Path`, `Size`, `CRC`) y rechazar rutas absolutas o con `..`;
  - comparar un archivo de `extraidos/` con su entrada del RAR, por tamaño y CRC32 calculado con `zlib.crc32`, y devolver además su SHA-256.

  Verificar con tests que arman un `.7z` o `.zip` sintético con `7z a` (o se saltean sin 7-Zip): un archivo que coincide, uno con un byte cambiado (CRC distinto), uno ausente, una ruta con `..` y 7-Zip ausente, comprobando el mensaje de instalación
- [x] 6.2 Implementar en `preparar_figshare.py`:
  - la verificación de los RAR contra `hito-2/fuentes.toml` (bytes y MD5) y `hito-2/fuentes.lock.json` (SHA-256);
  - la verificación con `rar7z.py` de los archivos seleccionados de `extraidos/`: el WAV estéreo completo de `wavs/Sin separar canales/S26_falta_separar_canales/` y las dos anotaciones de `phrases/S26/`;
  - la **selección** de S26 por lista de tareas (`seleccion`, inicialmente `["04"]`).

  Si algo falla, no se escribe nada. Verificar con tests sobre originales falsos, un lock y un listado armados en `tmp_path`: correctos, SHA-256 distinto, extraído con CRC distinto, tarea fuera de la selección ignorada, y nombre fuera del patrón
- [x] 6.3 Implementar la validación por grabación, con exclusión y motivo:
  - WAV completo de 16 kHz, **2 canales** y PCM16, leído completo;
  - las dos anotaciones presentes y bien formadas (criterios del Hito 2);
  - exceso terminal de 0,01 s o menos, con `TOLERANCIA_FIN_FIGSHARE_S` importada de `validar_muestra.py`;
  - **correspondencia entre canal y hablante:** cada canal del WAV estéreo se correlaciona más con su `wavs/S26/s26.objects.<TT>.channelN.wav` que con el otro, y la correlación se registra. Los WAV separados se usan solo para esto.

  Verificar con tests de cada motivo de exclusión (mono en vez de estéreo, 44,1 kHz, anotación de un canal faltante, exceso de 0,3 s, línea mal formada, canales invertidos) y con un test de paridad del patrón y las constantes con `hito-2/scripts/armar_muestra.py` (se saltea si faltan sus dependencias)
- [x] 6.4 Implementar la **conversión del WAV estéreo a mono** `(izquierda + derecha) // 2`, de 16 kHz y con los mismos cuadros, escrita con `wave` en `datos/figshare_test/S26/<grabacion>.wav`, sin modificar el original. Verificar con un test de un estéreo sintético: valores, cuadros y SHA-256 iguales en dos corridas, el original intacto, y que el mono pasa `entrada.validar_audio`
- [x] 6.5 Implementar en `evaluacion/referencia.py` la construcción del RTTM según la tabla del diseño: `#` excluido, texto con letras como habla, `politica_etiquetas.json` para etiquetas sin letras con fallo y listado si hay alguna sin clasificar, unión de intervalos del mismo canal, solapamiento entre canales conservado, y ajuste a la duración real de los fines que la exceden en 0,01 s o menos, registrando `{canal, linea, fin_original_s, fin_ajustado_s}`. Los tiempos del RTTM se escriben con la misma función de acotado de la tarea 2.3, sin superar la duración real. Agregar el modo `--inventario`. Verificar con tests de cada fila de la tabla, de los escenarios de "Política de etiquetas de la referencia" y de un fin que, redondeado a 3 decimales, superaría la duración real de la mezcla
- [x] 6.6 Implementar la validación de la referencia antes de las métricas (`0 <= start < end <= duración`, hablante, duplicados y al menos un segmento de habla; si no se cumple, `der_estricto`, `der_tolerancia` y `jer` en `null` con el motivo) y el **indicador de cobertura** por canal, según el design §11: energía en ventanas de 30 ms, piso = percentil 20 en `#`, umbral = piso + 12 dB, tramos de 0,3 s o más fuera de la habla del otro canal, y proporción del habla anotada con energía baja. El indicador es solo un indicio y no cambia la referencia. Verificar con tests de una referencia utilizable, una sin habla y una con un segmento fuera de la duración, y con un estéreo sintético con un tono no anotado dentro de un `#` (el indicador lo detecta) y otro sin habla sin anotar (0 s)
- [x] 6.7 Implementar el manifiesto `evaluacion/figshare_test.manifest.json` con las secciones `contenido` (determinista, serialización canónica, duraciones en cuadros) y `ejecucion` (variable) y `contenido_sha256` (sección 11 del diseño, sin texto de las anotaciones), y `--verificar`, que ignora `ejecucion`. Verificar con tests:
  - dos preparaciones de los mismos originales sintéticos, con `ejecucion` alterada a propósito (otra fecha y otra versión de 7-Zip simulada), dan `contenido` idéntico byte a byte y el mismo `contenido_sha256`;
  - cambiar una clasificación de `politica_etiquetas.json` cambia `contenido`;
  - cada `fin_original_s` de `ajustes_fin` coincide con la línea de la anotación sintética;
  - `--verificar` falla nombrando la grabación si se altera una mezcla, y no falla si solo cambia `ejecucion`;
  - los originales tienen el mismo SHA-256 antes y después
- [x] 6.8 **Con autorización.** Correr `--inventario` sobre la selección `["04"]`, que no tiene etiquetas sin letras: las de S26 (`-?`, `?-`) aparecen en las tareas 09 y 12. Después, correr la preparación de `s26.objects.04` con los archivos de `extraidos/`, sin descargar nada. Verificar:
  - que el manifiesto tiene solo `figshare_v2_S26_objects_04` como válida, con CRC32 y SHA-256 de sus archivos, la correlación canal ↔ hablante y el indicador de cobertura;
  - que el WAV mono dura 52,271 s (836 333 cuadros) y pasa `entrada.validar_audio`;
  - que `--verificar` pasa;
  - que `git status` muestra solo el manifiesto y la política;
  - que el procedimiento queda documentado en el README.

  Ampliar después la selección a todo S26, con autorización y con las etiquetas clasificadas en `politica_etiquetas.json` con aprobación del equipo
- [ ] 6.9 Completar el README: FFmpeg 7.1.1 *shared* (dependencia compartida; en Windows, `.pth` con `os.add_dll_directory`), 7-Zip, las dos variantes de PyTorch, el token propio, el uso de la CLI y de la función, contrato, meta y archivo de error, el contrato para el orquestador, las tolerancias (0,05 s de la salida y 0,01 s de la referencia), la preparación del dataset, y una tabla de **qué corre sin GPU y qué en el equipo con GPU**. Verificar siguiendo el README desde un entorno nuevo hasta pasar el nivel 1, el nivel 2 y `--verificar`

  > **Revisión del 08/11/2026: queda sin marcar.**
  > - **Documentado en el README:** todos los contenidos que pide la tarea, incluidas las secciones "Estado de la tarea 6.9" y "Pendiente en GPU".
  > - **Verificado con el entorno actual, sin reinstalar:**
  >   - `verificar_entorno.py`: 0 fallas y 0 avisos;
  >   - el nivel 1;
  >   - el nivel 2: 6 pruebas pasan, y los tres `diarization.json` coinciden byte a byte con los de la tarea 5.3;
  >   - `--verificar` con las 25 grabaciones de S26.
  > - **Falta:** la instalación **desde un entorno nuevo** siguiendo solo el README (`.venv`, PyTorch, `requirements.txt` + `constraints.txt`, FFmpeg y `.env`) y repetir esas cuatro verificaciones. Requiere reinstalar las dependencias. Se propone que lo haga otro integrante en su máquina, por ejemplo en la tarea 7.4.

## 7. Evaluación de calidad (CPU o GPU) y pruebas propias de CUDA

> **Una tarea por vez.** La máquina de desarrollo solo tiene CPU. Correr el modelo, la corrida diagnóstica, sesiones completas o pruebas pesadas requiere autorización explícita antes de cada paso. El dataset ya está extraído y no se descarga.
>
> **Pendiente, sin tarea asignada todavía:** comparar con S21–S23, donde cada canal mono tiene una voz predominante y otra más lejana, para evaluar cómo responde pyannote ante diferencias de intensidad entre hablantes.

- [x] 7.1 Implementar `evaluacion/der.py` con las métricas de calidad, cada una con su propia instancia y acumulada por sesión:
  - `der_estricto` (`collar=0.0`) y `der_tolerancia` (criterio NIST, `collar=0.5` en pyannote = ±0,25 s por lado, a partir de `TOLERANCIA_NIST_POR_LADO_S = 0.25`), ambas con `skip_overlap=False`;
  - **`jer`** (`JaccardErrorRate`, `collar=0.0`, `skip_overlap=False`), con el error de cada hablante de la referencia.

  Cada métrica va en su bloque, con `metrica`, `criterio`, `herramienta`, `collar_pyannote_s`, `tolerancia_por_lado_s` e `incluye_solapamiento`. Los DER traen además sus **componentes**, en segundos y como proporción. El módulo calcula también la **dispersión** sobre grabaciones (mediana, cuartiles y peor grabación) y la **cantidad de hablantes** (referencia, detectados y si coinciden). Todas las métricas quedan en `null` con el motivo si la referencia no es utilizable. Verificar con tests de nivel 1 sobre referencias e hipótesis armadas a mano:
  - un caso con DER conocido para cada métrica;
  - un borde desplazado 0,2 s: `der_estricto > 0` y `der_tolerancia == 0`, lo que confirma ±0,25 s y no ±0,125 s;
  - un borde desplazado 0,4 s: `0 < der_tolerancia < der_estricto`;
  - un solapamiento que cuenta en las dos;
  - que el reporte trae `collar_pyannote_s` 0,0 y 0,5, `tolerancia_por_lado_s` 0,0 y 0,25, y `herramienta` con la versión de `pyannote.metrics`, y que el README describe `der_tolerancia` como "DER de pyannote.metrics con tolerancia NIST", no como un resultado de `md-eval`;
  - que `jer` es 0 con una hipótesis perfecta y mayor que 0 con un hablante mal asignado;
  - que los componentes suman el error total;
  - que la dispersión (mediana y cuartiles) se calcula bien sobre una lista conocida;
  - que `cantidad_coincide` es `false` cuando la hipótesis tiene 3 hablantes y la referencia 2.
- [x] 7.2 Escribir `tests/test_evaluacion_calidad.py` (marker `calidad`, registrado en `conftest.py`), que corre en **CPU o GPU** con `device="auto"`:
  - ejecuta `--verificar`;
  - diariza cada grabación válida de la selección (al principio solo `s26.objects.04`), usando el **WAV mono derivado**, en una corrida **`principal`** (sin `num_speakers`). La **`diagnostico_num_speakers`** (`num_speakers=2`) corre solo con `--diagnostico`; si no se pide, queda en `null` con el motivo "no solicitada";
  - comprueba el contrato (A) de las dos;
  - calcula DER estricto y con tolerancia, JER, componentes y cantidad de hablantes (B), y la dispersión y los acumulados por sesión y en total;
  - registra `dispositivo` y `tiempo_s`;
  - escribe `tests/reportes/calidad_S26.json` y `tests/reportes/calidad_total.json`, este último con el bloque `limitaciones` (que incluye la transcripción posiblemente incompleta y el indicador de cobertura) y la dispersión en `null` mientras haya una sola grabación.

  **Primera ejecución, con autorización:** `s26.objects.04`, en CPU, solo la corrida principal, registrando DER, JER y tiempos. La corrida diagnóstica y la ampliación a todo S26 se autorizan aparte. Verificar que sin el dataset preparado, `pytest -m calidad -rs` se saltea con su motivo
- [ ] 7.3 Escribir `tests/test_evaluacion_gpu.py` (marker `gpu`), solo con las **pruebas propias de CUDA**:
  - corre cada grabación válida en `auto`, midiendo `memory_allocated()` antes y después y el pico;
  - comprueba `dispositivo == "cuda"` y que la memoria quede dentro de 64 MiB;
  - corre en `cpu` la primera grabación válida de la selección como **compatibilidad funcional**: comprueba que termina bien y cumple el contrato, y solo registra la cantidad de hablantes y de segmentos y el tiempo de cada dispositivo, sin compararlos;
  - escribe `tests/reportes/gpu_<sesion>.json`.

  Verificar en la máquina de desarrollo que `pytest -m gpu -rs` se saltea con el motivo "sin CUDA"

  > **Pendiente (08/11/2026).** La responsable de la Etapa 2 no tiene GPU en su máquina. La prueba la tienen que escribir y ejecutar integrantes con GPU NVIDIA.
  >
  > **Actualización (09/11/2026): sigue sin marcar.**
  > - Una compañera midió **a mano**, en una RTX 4060 Ti, un incremento residual de 8,12 MiB después de `diarizar()` (límite de 64 MiB) y un pico de 1628,5 MiB.
  > - Esa medición **no reemplaza** el test automatizado: `tests/test_evaluacion_gpu.py` todavía no existe, y tampoco el reporte `gpu_<sesion>.json` ni la compatibilidad funcional CPU/GPU dentro del test.
  > - Detalle en `registro-pruebas.md`, sección "Pruebas en GPU".
- [ ] 7.4 **(Pendiente para un integrante con GPU NVIDIA.)** Instalar el wheel cu128, FFmpeg (serie 4 a 7, idealmente 7.1.1 *shared*) y 7-Zip siguiendo el README, pasar `verificar_entorno.py --gpu` sin fallas, preparar o copiar el dataset y pasar `--verificar` con los mismos SHA-256, y correr `pytest PoC/paso2_diarizacion` y `pytest PoC/paso2_diarizacion -m gpu`. Verificar que los reportes de la selección de S26 tienen `dispositivo: "cuda"`, la memoria dentro del margen y `vram_pico_mib`, y que la compatibilidad CPU/GPU cumple el contrato. Registrar en el README las versiones, la GPU y los tiempos

  > **Pendiente (08/11/2026).** Sin GPU en la máquina de desarrollo, la ejecutan compañeros del equipo. Puede servir también para cerrar la verificación desde un entorno nuevo de la tarea 6.9.
  >
  > **Actualización (09/11/2026): avance parcial, sigue sin marcar.** Una compañera, en su equipo (Ubuntu 24.04, Python 3.12.3, RTX 4060 Ti de 16 GB, torch 2.8.0+cu128, pyannote.audio 4.0.7), informó:
  > - `verificar_entorno.py` sin fallas;
  > - los derivados con los mismos SHA-256 del manifiesto;
  > - `pytest -m calidad` en CUDA con 25/25 grabaciones (tarea 7.7);
  > - la medición manual de memoria.
  >
  > **Falta:**
  > - `pytest -m gpu`, que depende de la 7.3;
  > - la compatibilidad CPU/GPU dentro de ese test;
  > - informar el nivel 1 en su equipo;
  > - registrar en el README las versiones, la GPU y los tiempos.
  >
  > No consta que la instalación haya seguido solo el README desde un entorno nuevo, así que tampoco cierra la 6.9.
- [x] 7.7 **(Registrada el 09/11/2026; la ejecutó una compañera en su equipo.)** Evaluación de calidad de las 25 grabaciones de S26 en **CUDA** con `pytest -m calidad`, con la corrida principal sin `num_speakers` y sin reutilizar resultados.

  Verificado según su informe:
  - las 25/25 grabaciones se procesaron en CUDA;
  - los WAV mono y los RTTM coinciden con el manifiesto publicado;
  - el test terminó satisfactorio;
  - DER estricto 23,15 %, DER NIST 12,32 % y JER 40,02 %, iguales a los de CPU con 2 decimales;
  - la cantidad de hablantes es correcta en 24/25;
  - la inferencia tardó 79,146 s para 1821,246 s de audio.

  **Evidencia:** el informe de la compañera, transcripto en `registro-pruebas.md`, sección "Pruebas en GPU". Sus reportes `calidad_*.json` y sus hipótesis **no están versionados**. Para que la comparación CPU/GPU por grabación sea reproducible, falta publicarlos (ver `evaluacion/publicar_resultados.py`).
- [x] 7.6 **(Autorizada el 08/11/2026.)** Ampliar la preparación y la evaluación de calidad a las 25 tareas de S26, en CPU, solo con la corrida principal (sin `num_speakers`):
  - admitir 1 cuadro de más al final en los WAV separados, registrando la diferencia;
  - clasificar `-?` y `?-` como `habla` en `politica_etiquetas.json`;
  - reutilizar la corrida compatible de `s26.objects.04`;
  - agregar al reporte la duración, el habla de la referencia y la superpuesta, la cobertura NIST, el error con y sin solapamiento, los estadísticos por grabación (media, mediana, mínimo, máximo y desviación estándar) y la tabla ordenada por DER.

  Verificar:
  - los tests de nivel 1 de la tolerancia de cuadros, la política, los estadísticos, la descripción de la referencia, el solapamiento (que las dos regiones sumen el DER estricto) y la cobertura NIST;
  - `--verificar` con las 25 grabaciones;
  - los originales sin cambios;
  - `pytest -m calidad` en verde.
- [ ] 7.5 Comprobar con Matías que un `diarization.json` generado por la Etapa 2 lo consume la Etapa 4 sin transformaciones; verificar que `contrato.py` da cero violaciones sobre ese archivo en el entorno de la interfaz, sin torch

  > **Pendiente (08/11/2026):** revisión y validación del equipo, con quien desarrolla la Etapa 4.

## Workflow follow-up

- (08/11/2026) OpenSpec de la Etapa 2 se trasladó de `openspec/` en la raíz a `PoC/paso2_diarizacion/openspec/`, para separarlo de otras etapas. Los archivos se movieron sin cambios y `openspec validate --strict` pasa. El CLI se ejecuta desde `PoC/paso2_diarizacion/`.

- Acordar con Felipe la ubicación del entorno compartido de las etapas 2 y 3 y actualizar el README.
- Avisar a quien tome el orquestador que debe decidir por el código de salida o por `DiarizacionError`.
- Archivar el change cuando los niveles 1 y 2 y la preparación pasen en la máquina de desarrollo y los reportes del nivel 3 estén revisados.
