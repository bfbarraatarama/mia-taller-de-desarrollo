# Hito 2 — Dataset y EDA de viabilidad

**Equipo:** Luisa, Bruno, Matías y Felipe · [Canvas](../canvas.md)
**Decisión:** ajustar el alcance: evaluación modular de transcripción, separación de hablantes y minutas; evaluación integral en castellano con reuniones propias. No se entrenan ni evalúan modelos en este hito.

## Entregables

| Entregable | Archivo |
|---|---|
| 1. Mapa de fuentes | [`1-mapa-de-fuentes.md`](1-mapa-de-fuentes.md) |
| 2. EDA y *leakage* | [`2-eda-de-viabilidad.md`](2-eda-de-viabilidad.md), [`notebooks/eda_viabilidad.ipynb`](notebooks/eda_viabilidad.ipynb) |
| 3. Datasheet abreviado | [`3-datasheet.md`](3-datasheet.md) |
| 4. Veredicto y plan básico | [`4-veredicto.md`](4-veredicto.md) |

Evidencia auxiliar: [`niveles-a-priori.md`](niveles-a-priori.md) (25 niveles inalterados), [`resultados_eda.csv`](resultados_eda.csv), [`resultados_leakage.csv`](resultados_leakage.csv) (cinco búsquedas), [`figuras/`](figuras/), [`muestra/`](muestra/), [`resumen-puesta-en-comun.md`](resumen-puesta-en-comun.md). El notebook conserva las mediciones históricas e integra Common Voice 26 Rioplatense, CALLHOME Spanish y UBA Games Figshare v2.

## Qué permite reproducir este repositorio

**Sin credenciales ni audio:** consultar los documentos, el notebook con sus salidas guardadas, las figuras, los resultados CSV y las tablas históricas versionadas de `muestra/`. Las tablas históricas y sus índices no equivalen a todos los archivos originales. Se puede comprobar la integridad formal de la entrega con el bloque «Inspección sin originales» de abajo, pero **no** volver a ejecutar el notebook completo desde cero.

**Con los originales y autorizaciones correspondientes:** descargar los archivos de las versiones fijadas, regenerar las cinco tablas normalizadas, validarlas, repetir la auditoría acústica y ejecutar el notebook completo. CALLHOME requiere acceso individual autorizado a TalkBank/Hugging Face; Common Voice requiere una cuenta y aceptación de términos de Mozilla Data Collective. Ni la posesión del repositorio ni el acceso al código otorgan esos permisos. Los originales restringidos no se redistribuyen. La adquisición puede fallar si una fuente deja de estar disponible: registrar la incidencia, no sustituir silenciosamente la versión.

La procedencia y las restricciones se describen en [`ADQUISICION.md`](ADQUISICION.md), [`muestra/LICENCIAS.md`](muestra/LICENCIAS.md), [`fuentes.toml`](fuentes.toml) y [`fuentes.lock.json`](fuentes.lock.json). El contrato común de los datos se documenta en [`esquema-normalizado.md`](esquema-normalizado.md).

## Reproducción completa en Linux

Ejecutar **todos los comandos desde la raíz del repositorio**, no desde `hito-2/`. Se utilizó Python 3.12. Son necesarios `ffmpeg`, `ffprobe` y la biblioteca compartida del sistema `libarchive` (para los dos RAR de Figshare), además de acceso a Internet y espacio suficiente para varios gigabytes de originales y temporales. Verificar su disponibilidad antes de empezar:

```bash
python3 --version
ffmpeg -version
ffprobe -version
ldconfig -p | grep libarchive
```

En otras plataformas, instalar herramientas equivalentes y verificar sus rutas; el procedimiento integral se comprobó en Linux, no se garantiza idéntico comportamiento de los comandos del sistema en Windows.

### 1. Preparar el entorno y comprobar el código

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r hito-2/requirements.txt -r hito-2/requirements-adquisicion.txt
.venv/bin/python -m unittest discover -s hito-2/tests -v
```

Las pruebas no descargan originales y deben finalizar sin fallos (72 pruebas en el estado validado el 13/10/2026). Instalar las dependencias del **Hito 2**, no las del `requirements.txt` de la raíz, que corresponde a otro proyecto. Las dependencias declaran rangos, no un bloqueo exacto de todas las versiones; por eso no se promete igualdad binaria de archivos derivados entre entornos distintos.

### 2. Adquirir y verificar los originales fijados

Primero obtener las credenciales personales `MDC_API_KEY` y `HF_TOKEN` como indica [`ADQUISICION.md`](ADQUISICION.md), sin registrarlas en Git ni compartirlas. **No basta con el grupo `principales`**: CALLHOME es obligatorio para las cinco tablas normalizadas y se descarga explícitamente.

```bash
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py principales callhome
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py comprobar
```

`principales` comprende anotaciones históricas, OpenSLR 61, CORdeBA, Common Voice y Figshare v2; `callhome` añade los cinco Parquet de acceso restringido. `comprobar` exige el inventario completo de `fuentes.lock.json` (43 archivos en la revisión usada), no solo las fuentes de acceso público. **No se debe forzar el lock ni cambiar hashes** para hacer pasar una descarga. La distribución UBA Games original de CONICET es diferente de Figshare v2 y no se utiliza en este recorrido.

### 3. Construir y validar la muestra normalizada

Las tablas históricas (AMI, ICSI, VoxConverse, Humyn, OpenSLR y CORdeBA) ya están versionadas y se utilizan como base del EDA. Para reconstruir **también** la muestra histórica desde sus originales, ver la sección opcional siguiente antes de ejecutar este paso.

```bash
.venv/bin/python -I hito-2/scripts/armar_muestra.py normalizado
.venv/bin/python -I hito-2/scripts/validar_muestra.py --componente todos
```

El constructor regenera las muestras derivadas de OpenSLR, CORdeBA y Figshare, normaliza las cinco fuentes seleccionadas, verifica los hashes de entrada y genera `muestra/normalizado/` y el informe de anomalías CALLHOME. El validador debe informar **cinco tablas y cero incidencias**. Los dos intervalos originales CALLHOME inválidos se documentan; no se modifican tiempos ni se inventan etiquetas.

### 4. Auditar la aptitud acústica

```bash
.venv/bin/python -I hito-2/scripts/auditar_aptitud.py
```

Regenera `hito-2/muestra/normalizado/aptitud/INFORME_B.json` y `RESULTADOS_B.csv` mediante una selección determinista. La auditoría verifica decodificación real, no WER ni DER. En la ejecución de referencia se inspeccionaron 106 unidades heterogéneas y se decodificaron 105; las nueve mezclas Figshare y los 44 FLAC OpenSLR **no** prueban el audio íntegro de sus corpus. La anomalía temporal de CALLHOME debe leerse en el EDA, sin extrapolar su frecuencia a los 140 registros.

### 5. Ejecutar el EDA y comprobar las salidas

```bash
.venv/bin/jupyter nbconvert --to notebook --execute --inplace hito-2/notebooks/eda_viabilidad.ipynb
```

Se regeneran `hito-2/resultados_eda.csv`, `hito-2/resultados_leakage.csv`, las figuras que produce el notebook y sus salidas de celda. La actualización del notebook **requiere** los TSV originales de Common Voice, las tablas de `muestra/normalizado/` y ambos resultados acústicos; ejecutar solo con el clon y sin esos archivos dará un error, y no es evidencia de un fallo en los datos históricos.

Comprobar que el proceso produjo el conjunto completo de resultados:

```bash
.venv/bin/python - <<'PY'
import csv
import json
from pathlib import Path

h = Path('hito-2')
with (h / 'resultados_eda.csv').open(encoding='utf-8', newline='') as f:
    niveles = list(csv.DictReader(f))
with (h / 'resultados_leakage.csv').open(encoding='utf-8', newline='') as f:
    fugas = list(csv.DictReader(f))
assert len(niveles) == len({r['id'] for r in niveles}) == 25
assert {r['id'] for r in fugas} == {'L1', 'L2', 'L3', 'L4', 'L5'}
assert len(fugas) == 5
normal = h / 'muestra/normalizado'
manifiesto = json.loads((normal / 'MANIFIESTO_NORMALIZADO.json').read_text())
assert len(manifiesto['tablas']) == 5
assert (normal / 'aptitud/INFORME_B.json').is_file()
assert (normal / 'aptitud/RESULTADOS_B.csv').is_file()
print('EDA: 25 niveles, 5 búsquedas de leakage; normalización y auditoría disponibles')
PY
```

Esta comprobación es estructural: no sustituye la lectura de los resultados y sus limitaciones en los cuatro documentos oficiales. Los archivos derivados restringidos o pesados (`.cache/`, `muestra/normalizado/` y audio) se excluyen de Git. Los CSV de resultados y el notebook ejecutado **sí** deben quedar versionados para que el docente pueda inspeccionar la evidencia sin adquirir datos restringidos.

### Reconstrucción adicional de la muestra histórica (opcional)

Si se requiere regenerar además los índices y las tablas históricas que **ya se incluyen** en `muestra/`, antes del paso 3 adquirir Humyn y los extractos de AMI/ICSI, y ejecutar el constructor histórico sin argumentos:

```bash
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py humyn audio
.venv/bin/python -I hito-2/scripts/descargar_fuentes.py comprobar
.venv/bin/python -I hito-2/scripts/armar_muestra.py
```

Esta operación necesita las fuentes históricas y sus servicios externos, por lo que no se presupone disponible para todos los lectores. El constructor histórico sustituye `muestra/MANIFIESTO.json`; ejecutar **después** `armar_muestra.py normalizado` vuelve a incorporar su procedencia al manifiesto. Antes de versionar cambios, contrastar los datos históricos regenerados con la muestra original y revisar diferencias; no atribuir paridad automática.

## Inspección sin originales ni credenciales

```bash
python3 - <<'PY'
import csv
from pathlib import Path
h = Path('hito-2')
with (h / 'resultados_eda.csv').open(encoding='utf-8', newline='') as f:
    niveles = list(csv.DictReader(f))
with (h / 'resultados_leakage.csv').open(encoding='utf-8', newline='') as f:
    fugas = list(csv.DictReader(f))
assert len(niveles) == 25 and len({r['id'] for r in niveles}) == 25
assert len(fugas) == 5 and {r['id'] for r in fugas} == {'L1', 'L2', 'L3', 'L4', 'L5'}
assert (h / 'notebooks/eda_viabilidad.ipynb').is_file()
print('Entregables de EDA presentes: 25 niveles y 5 búsquedas; resultados guardados')
PY
```

El notebook guardado permite consultar las celdas y sus salidas sin volver a descargarlas. La prueba anterior verifica que la entrega está completa **en estructura**; no recalcula las estadísticas desde los originales. Los archivos oficiales son el mapa de fuentes, EDA, datasheet y veredicto enlazados al inicio.
