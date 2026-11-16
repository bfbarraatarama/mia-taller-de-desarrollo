# Evaluación de la Etapa 2

Contiene la preparación del dataset de test de UBA Games (sesión S26, 25 grabaciones) y las métricas de calidad (DER y JER). Cada pieza corresponde al grupo 6 y a las tareas 7.x de [`../../docs/diarizacion/openspec/changes/etapa-2-diarizacion/tasks.md`](../../docs/diarizacion/openspec/changes/etapa-2-diarizacion/tasks.md).

- **Resultados y metodología:** [`EVALUACION_S26.md`](EVALUACION_S26.md).
- **Procedimiento de preparación y evaluación:** en este documento.
- **Estado y mediciones históricas:** [registro de desarrollo](registro-desarrollo.md).
- **Contratos y uso del módulo:** [guía técnica](../../docs/diarizacion/README.md).

| Archivo | Estado | Qué hace |
|---|---|---|
| `src/rar7z.py` | ✅ tarea 6.1 | Localiza 7-Zip y lista los RAR (ruta, tamaño y CRC32) sin extraer. Rechaza rutas inseguras, compara los archivos de `extraidos/` con su entrada y calcula su SHA-256 |
| `preparar_figshare.py` | ✅ tareas 6.2 a 6.4, 6.7, 6.8 y 7.6 | Opciones de la línea de comandos:<br>· `--verificar-entradas`: verifica los RAR y los archivos extraídos.<br>· `--validar`: decide si cada grabación es válida o queda excluida; admite 1 cuadro de más al final en los WAV separados.<br>· `--inventario`: lista las etiquetas sin letras.<br>· `--preparar`: genera el mono `(L + R) // 2`, el RTTM, la cobertura y el manifiesto.<br>· `--verificar`: comprueba los derivados contra el manifiesto.<br>Las operaciones sobre originales aceptan `--seleccion 01 … 25`; `--verificar` comprueba el manifiesto vigente |
| `referencia.py` | ✅ tareas 6.5 y 6.6 | Arma la referencia RTTM a partir de las anotaciones:<br>· clasifica cada línea (`#`, texto con letras o etiqueta de la política);<br>· une los intervalos de un mismo canal y conserva el solapamiento entre canales;<br>· ajusta los fines dentro de la tolerancia.<br>También valida la referencia antes de calcular las métricas y calcula el indicador de cobertura |
| `der.py` | ✅ tareas 7.1 y 7.6 | DER estricto, DER con tolerancia NIST, JER con el error por hablante y componentes. Además calcula el acumulado ponderado, los estadísticos por grabación, la cantidad de hablantes, la cobertura NIST y el error con y sin solapamiento |
| `publicar_resultados.py` | ✅ | Copia los reportes de `evaluacion/diarizacion/reportes/` y las hipótesis a `resultados/`, verificando SHA-256 y que no haya rutas absolutas |
| `politica_etiquetas.json` | versionado | `-?` y `?-` = `habla` (decisión del 08/11/2026) |
| `figshare_test.manifest.json` | versionado | `contenido`, que es determinista e incluye su `contenido_sha256`, y `ejecucion`, que varía. No incluye el texto de las anotaciones |
| `resultados/` | versionado | `calidad_S26.json`, `calidad_total.json` y `hipotesis_S26/<recording_id>.json` (las 25 salidas de la corrida principal en CPU). Además, `nivel2/integracion_*.json`: los tres reportes del nivel 2, evidencia de la tarea 5.5 (véase el [registro de desarrollo](registro-desarrollo.md#verificación-básica-del-nivel-2-tarea-55)) |
| `EVALUACION_S26.md` | versionado | Documentación de la evaluación de S26 |

Los derivados (WAV mono y RTTM) se escriben en `evaluacion/diarizacion/datos/figshare_test/S26/`, que git ignora.

## Tolerancias

| Tolerancia | Valor | De qué es | Dónde se aplica |
|---|---|---|---|
| `tolerancia_fin_s` (salida) | 0,05 s | campo heredado del meta de `diarization.json` | solo se registra; los tiempos se recortan siempre a la duración real (véase [normalización de tiempos](../../docs/diarizacion/README.md#normalización-de-los-tiempos)) |
| `TOLERANCIA_FIN_FIGSHARE_S` (referencia) | 0,01 s | exceso terminal admitido en las anotaciones de Figshare; **se importa** de `hito-2/scripts/validar_muestra.py` | una grabación cuyo `.phrases` termina más de 0,01 s después del WAV se excluye; si termina 0,01 s o menos después, su fin se ajusta a la duración real en la referencia y el ajuste se registra |
| orden | 1e-4 s | `start >= fin_anterior - 1e-4` (criterio del Hito 2) | validación de las anotaciones |
| NIST | ±0,25 s por lado (`collar=0.5` en pyannote) | `der_tolerancia` | evaluación de calidad (nivel 3a) |

## Dataset de test (Figshare, sesión S26)

Prepara la referencia para medir DER y JER con UBA Games (Figshare v2, CC BY 4.0). La muestra versionada comprende las **25 grabaciones de S26**. El valor predeterminado `04` de la CLI sirve para exploración, no para regenerar el manifiesto vigente. Usa los archivos **ya descargados y extraídos** en `hito-2/.cache/uba_games/figshare-v2/`: no descarga, no extrae y no modifica nada de esa carpeta.

**7-Zip** se usa solo para **listar** los RAR (`7z l -slt`), nunca para extraer. Se busca la variable `SIETE_ZIP`, después `7z`/`7zz`/`7za` en el `PATH` y por último `%ProgramFiles%\7-Zip\7z.exe`. Si no está, el mensaje explica cómo instalarlo.

Desde la raíz del repo (`-X utf8` evita problemas de consola en Windows):

```powershell
$py = ".venv/Scripts/python.exe"
$sel = 1..25 | ForEach-Object { '{0:D2}' -f $_ }
& $py -X utf8 -m evaluacion.diarizacion.preparar_figshare --verificar-entradas --seleccion $sel  # RAR y extraídos (solo lectura)
& $py -X utf8 -m evaluacion.diarizacion.preparar_figshare --validar --seleccion $sel             # + validez de cada grabación
& $py -X utf8 -m evaluacion.diarizacion.preparar_figshare --inventario --seleccion $sel          # etiquetas sin letras y su clase
& $py -X utf8 -m evaluacion.diarizacion.preparar_figshare --preparar --seleccion $sel            # escribe mono, RTTM y manifiesto
& $py -X utf8 -m evaluacion.diarizacion.preparar_figshare --verificar           # derivados contra el manifiesto
```

La preparación debe utilizar la selección completa `01` a `25`. La política versionada clasifica `-?` (tarea 09) y `?-` (tarea 12) como habla. Modificar la selección o la política requiere acuerdo del equipo y una nueva procedencia. `--verificar` lee la selección del manifiesto existente. Después de preparar, comprobar que `contenido_sha256` coincide con el valor versionado; no incorporar cambios de manifiesto o resultados publicados automáticamente.

En Linux, desde la raíz:

```bash
.venv/bin/python -m evaluacion.diarizacion.preparar_figshare --preparar --seleccion {01..25}
.venv/bin/python -m evaluacion.diarizacion.preparar_figshare --verificar
```

Para datos ya preparados, ejecutar únicamente `--verificar`. Antes de preparar desde cero, mantener el manifiesto versionado como referencia: comparar `contenido_sha256` con el valor de Git después de la preparación. Puede cambiar la sección `ejecucion`; no incluir ese cambio incidental en un commit.

**Pasos de `--preparar`.** Se validan las fuentes antes de generar derivados; no se promete una transacción multiarchivo ante interrupciones.
1. Verifica `phrases.rar` y `wavs.rar` contra `hito-2/fuentes.toml` (bytes y MD5) y `fuentes.lock.json` (SHA-256).
2. Verifica cada archivo usado de `extraidos/` (tamaño y CRC32) contra el listado de su RAR y calcula su SHA-256.
3. Valida cada grabación. Las que no cumplen quedan `excluida`, con su motivo:
   - WAV completo estéreo, de 16 kHz y PCM16, leído completo;
   - anotaciones de los dos canales bien formadas;
   - exceso terminal de 0,01 s o menos;
   - correspondencia canal ↔ hablante: cada canal se correlaciona más con su `wavs/S26/…channelN.wav` que con el otro.
4. Escribe en `evaluacion/diarizacion/datos/figshare_test/S26/`, que git ignora:
   - `<recording_id>.wav`, el mono `(izquierda + derecha) // 2`, de 16 kHz, PCM16 y con los mismos cuadros, que es la entrada de pyannote;
   - `<recording_id>.rttm`, con los hablantes `figshare_v2_S26_canal1` y `figshare_v2_S26_canal2`:
     - `#` se excluye y el texto con letras es habla;
     - las etiquetas sin letras siguen la política;
     - los intervalos del mismo canal superpuestos o contiguos se unen;
     - el solapamiento entre canales se conserva;
     - los tiempos tienen 3 decimales y nunca superan la duración real.
5. Calcula el **indicador de cobertura** por canal. Es solo un indicio y no cambia la referencia. Busca dos cosas:
   - energía alta dentro de un `#` y fuera de la habla del otro canal, en tramos de 0,3 s o más;
   - habla anotada con energía baja.
6. Escribe `evaluacion/diarizacion/figshare_test.manifest.json`, que se versiona y no contiene el texto de las anotaciones. Tiene dos secciones:
   - `contenido`: determinista, con su `contenido_sha256`;
   - `ejecucion`: fecha, sistema, Python, 7-Zip y commit, que no se comparan.

`--verificar` recalcula `contenido_sha256` y los SHA-256 del mono y del RTTM. Si algo no coincide, falla nombrando la grabación. El nivel 3 lo ejecuta antes de evaluar.

**Resultado histórico de la preparación inicial de `s26.objects.04` (08/11/2026, no es la huella del manifiesto actual):**
- Grabación válida: 836 333 cuadros.
- Correlación de cada canal con su WAV separado: 0,99996 y 0,99999.
- Exceso terminal: 0,0092 s en los dos canales. Los dos excesos están en intervalos `#`, así que no hubo ajustes.
- Referencia: 33 segmentos (15 del canal 1 y 18 del canal 2), utilizable.
- Cobertura: 0 s de posible habla sin anotar. La proporción de habla anotada con energía baja es 8,6 % en el canal 1 y 6,6 % en el canal 2. Probablemente son pausas dentro de las frases, pero no se revisó a mano.
- `contenido_sha256` = `3a5323680f095f7ae2545da0cd2c3d10a09488f3ee7a9712b37bed75d2783ec3`.

## Evaluación de calidad (nivel 3a)

Con `$py` definido como arriba:

```powershell
& $py -m pytest tests/diarizacion -m calidad -rs                 # corrida principal (sin num_speakers)
& $py -m pytest tests/diarizacion -m calidad -rs --diagnostico   # además, la diagnóstica con num_speakers=2
```

Primero ejecuta `--verificar`. Después diariza con `device="auto"` el WAV mono de cada grabación válida del manifiesto y compara la salida con el RTTM. La región evaluada (UEM) es `[0, duración]`, y el habla superpuesta se incluye en las tres métricas.

| Métrica | Qué es | Parámetros de `pyannote.metrics` |
|---|---|---|
| `der_estricto` | DER sin tolerancia: cada borde cuenta | `DiarizationErrorRate(collar=0.0, skip_overlap=False)` |
| `der_tolerancia` | **DER de pyannote.metrics con tolerancia NIST** de ±0,25 s por borde. **No** es un resultado de `md-eval`: reproduce su tolerancia por lado, pero no garantiza los mismos valores | `DiarizationErrorRate(collar=0.5, skip_overlap=False)` (en pyannote, `collar` es el ancho total) |
| `jer` | Jaccard Error Rate, con el error de cada hablante de la referencia | `JaccardErrorRate(collar=0.0, skip_overlap=False)` |

Cada DER trae sus componentes en segundos y como proporción de `total_referencia_s`: `falsa_alarma_s`, `habla_perdida_s` y `confusion_s`. El reporte trae además la cantidad de hablantes (referencia, detectados y si coinciden) y, con dos grabaciones o más, la dispersión: mediana, cuartiles y peor grabación. No hay umbral; los valores son la línea de base de la PoC.

Reportes, ignorados por git:
- `evaluacion/diarizacion/reportes/calidad_S26.json`: por grabación y acumulado de la sesión;
- `evaluacion/diarizacion/reportes/calidad_total.json`: acumulado, dispersión, cantidad de hablantes y `limitaciones`, que incluye el indicador de cobertura.

Las salidas de pyannote quedan en `evaluacion/diarizacion/reportes/calidad/<recording_id>/<corrida>/`.

Para verificar las evidencias publicadas sin inferencia y, por separado, obtener una nueva inferencia:

```bash
.venv/bin/python -m pytest tests/diarizacion -k resultados_publicados -rs
.venv/bin/python -m pytest tests/diarizacion -m calidad -rs --rehacer
```

La segunda orden requiere modelo y datos locales y escribe reportes de trabajo. La publicación mediante `.venv/bin/python -m evaluacion.diarizacion.publicar_resultados` reemplaza los resultados versionados; ejecutarla solo con acuerdo y después de revisar la procedencia. No forma parte de la verificación ordinaria.

**Resultados de S26** (25 grabaciones, detección automática de hablantes): metodología, tabla por grabación, análisis de errores y limitaciones en [`evaluacion/diarizacion/EVALUACION_S26.md`](EVALUACION_S26.md).
- **CPU, reproducible:** los reportes y las hipótesis versionados en `evaluacion/diarizacion/resultados/` son de la corrida en CPU. Se generaron mediante `python -m evaluacion.diarizacion.publicar_resultados`; la prueba `-k resultados_publicados` recalcula las métricas desde esos archivos y el RTTM local sin correr el modelo.
- **GPU, informado:** una compañera repitió la evaluación en CUDA y obtuvo las mismas métricas globales. Sus reportes no están versionados, así que no se pueden recalcular desde el repositorio (ver [Pruebas en GPU](registro-desarrollo.md#pruebas-en-gpu-tareas-73-74-y-77)).
