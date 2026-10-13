# Esquema normalizado de la muestra — Hito 2

## 1. Propósito y alcance

Este documento define el contrato común de datos para los componentes de transcripción automática (ASR) y diarización.

Las tablas particulares de cada fuente se conservan. Los adaptadores generan tablas normalizadas adicionales que permiten efectuar cálculos comparables sin introducir lógica específica de cada corpus en el notebook de EDA.

Las fuentes originales, sus revisiones y sus hashes se identifican mediante `fuentes.toml` y `fuentes.lock.json`. Las transformaciones y los artefactos generados deben quedar vinculados al manifiesto de la muestra.

Este contrato no determina la viabilidad de los datos, no modifica los niveles a priori y no asigna particiones de evaluación.

## 2. Convenciones comunes

### Identificadores

- `source`: identificador estable del corpus o distribución.
- `recording_id`: identificador de la unidad de audio dentro de `source`.
- `source_recording_id`: identificador original, conservado sin reinterpretar.
- `session_id`: sesión original, cuando pueda identificarse.
- `speaker_id`: identificador de hablante dentro de `source`, cuando exista información suficiente.
- `group_id`: agrupación destinada a preservar dependencias entre observaciones al construir particiones.

La clave de una grabación es `(source, recording_id)`. No se exige que `recording_id` sea globalmente único sin considerar la fuente.

`session_id`, `recording_id` y `speaker_id` no son intercambiables. Una sesión puede contener varias grabaciones, una grabación puede contener varios hablantes y un hablante puede aparecer en varias grabaciones.

Los identificadores de hablantes no se extienden a sesiones diferentes sin evidencia de que representan a la misma persona.

`group_id` debe fundamentarse en dependencias identificables. Si todavía no se conocen, el campo permanece nulo; no se genera una partición independiente por grabación como sustituto automático.

### Particiones

- `source_split`: partición proporcionada por la distribución original, si existe.
- `project_split`: partición de entrenamiento, desarrollo o evaluación definida por el proyecto.

Una partición original no se considera automáticamente válida para nuestro proyecto.

`project_split` permanece nulo hasta completar las búsquedas de leakage y aplicar la política de particionado. Su ausencia durante el EDA preliminar es esperada.

### Valores desconocidos

Los valores no disponibles se representan mediante nulos, no mediante identificadores inventados, cadenas vacías equivalentes a categorías válidas ni valores numéricos arbitrarios.

Debe distinguirse entre:

- Información que la fuente no proporciona.
- Información que todavía no se inspeccionó.
- Información que se intentó obtener pero resultó inválida.

Los indicadores de disponibilidad y validación documentan estas diferencias.

### Audio

- `duration_s`: duración en segundos, cuando se haya podido determinar.
- `audio_ref`: referencia trazable al audio original o derivado, cuando exista.
- `audio_status`: uno de `no_verificado`, `valido`, `ilegible` o `no_disponible`.

`audio_status = valido` exige una comprobación real de lectura y consistencia del audio, no solamente la existencia de un archivo o de una entrada en el manifiesto.

Las referencias de audio no deben incorporar rutas absolutas personales ni credenciales.

Las transformaciones acústicas deben quedar registradas y ser reproducibles desde los originales.

## 3. Transcripción automática

### `muestra/normalizado/asr_instancias.parquet`

Unidad: una grabación o fragmento potencialmente evaluable para ASR, identificado de manera inequívoca.

| Columna | Tipo | Descripción |
|---|---|---|
| `source` | texto | Fuente de procedencia |
| `recording_id` | texto | Grabación o fragmento |
| `source_recording_id` | texto | Identificador original |
| `session_id` | texto, nullable | Sesión de origen |
| `group_id` | texto, nullable | Grupo para prevenir leakage |
| `speaker_id` | texto, nullable | Hablante conocido |
| `duration_s` | real, nullable | Duración de la unidad |
| `audio_ref` | texto, nullable | Referencia al audio |
| `audio_status` | categoría | Estado de validación acústica |
| `reference_raw` | texto, nullable | Transcripción sin normalización lingüística |
| `reference_norm` | texto, nullable | Transcripción normalizada mediante una política documentada |
| `reference_origin` | texto, nullable | Archivo o campo de origen de la referencia |
| `reference_scope` | categoría | `recording`, `segment` o `unknown` |
| `language` | texto, nullable | Idioma o variedad documentada |
| `source_split` | texto, nullable | Partición original |
| `project_split` | texto, nullable | Partición del proyecto |

No se considera que una transcripción por turnos esté alineada temporalmente por el solo hecho de disponer del orden de esos turnos.

Si una fuente proporciona texto sin tiempos, se conserva esa limitación. No se inventan intervalos.

`reference_norm` solo se genera después de definir una política única de normalización adecuada a la evaluación. Debe mantenerse `reference_raw` para permitir otras políticas y verificar transformaciones.

La presencia de una transcripción no acredita por sí sola que sea completa, correcta o que corresponda temporalmente al audio.

### `muestra/normalizado/asr_hablantes.csv`

| Columna | Tipo | Descripción |
|---|---|---|
| `source` | texto | Fuente |
| `speaker_id` | texto | Identificador normalizado |
| `source_speaker_id` | texto, nullable | Identificador original |
| `speaker_scope` | categoría | `recording`, `session`, `source` o `unknown` |
| `session_id` | texto, nullable | Sesión a la que se limita la identidad |
| `recording_id` | texto, nullable | Grabación a la que se limita la identidad |

No se crean filas de hablantes cuando la identidad es desconocida.

Los atributos personales disponibles en algunas fuentes permanecen en sus tablas particulares y no se infieren a partir del audio, el nombre de archivo o el texto.

## 4. Diarización

### `muestra/normalizado/diarizacion_grabaciones.csv`

Unidad: una grabación con referencias de quién habla y cuándo, cuando estén disponibles.

| Columna | Tipo | Descripción |
|---|---|---|
| `source` | texto | Fuente |
| `recording_id` | texto | Grabación |
| `source_recording_id` | texto | Identificador original |
| `session_id` | texto, nullable | Sesión original |
| `group_id` | texto, nullable | Grupo para prevenir leakage |
| `duration_s` | real, nullable | Duración del audio |
| `audio_ref` | texto, nullable | Audio original o derivado |
| `audio_status` | categoría | Estado de validación acústica |
| `reference_origin` | texto, nullable | Origen de las anotaciones temporales |
| `source_split` | texto, nullable | Partición original |
| `project_split` | texto, nullable | Partición del proyecto |

El número de hablantes, las horas anotadas, la proporción de superposición y otras medidas se calculan a partir de las referencias normalizadas, sin almacenarlas como conclusiones de viabilidad independientes.

### `muestra/normalizado/diarizacion_segmentos.parquet`

Unidad: intervalo temporal de referencia asociado a una grabación.

| Columna | Tipo | Descripción |
|---|---|---|
| `source` | texto | Fuente |
| `recording_id` | texto | Grabación asociada |
| `speaker_id` | texto, nullable | Hablante asociado al intervalo |
| `start_s` | real | Inicio en segundos |
| `end_s` | real | Fin en segundos |
| `annotation_raw` | texto, nullable | Texto o etiqueta original |
| `is_silence_marker` | booleano, nullable | Indica silencio explícito de la fuente |
| `scored_as_speech` | booleano, nullable | Inclusión en la referencia de puntuación, cuando exista una política definida |
| `reference_origin` | texto, nullable | Archivo o campo original |

Los intervalos se conservan con sus tiempos originales. No se eliminan las superposiciones entre hablantes.

La existencia de una etiqueta no verbal no implica automáticamente que deba incluirse o excluirse de DER o JER.

`scored_as_speech` permanece nulo cuando la política todavía no permite clasificar inequívocamente un intervalo.

Los intervalos de silencio explícitos pueden conservarse para el EDA sin convertirse en segmentos de habla.

La generación de RTTM de evaluación constituye una transformación posterior, gobernada por la política de puntuación documentada.

### `muestra/normalizado/diarizacion_hablantes.csv`

| Columna | Tipo | Descripción |
|---|---|---|
| `source` | texto | Fuente |
| `speaker_id` | texto | Identificador normalizado |
| `source_speaker_id` | texto, nullable | Identificador original |
| `speaker_scope` | categoría | `recording`, `session`, `source` o `unknown` |
| `session_id` | texto, nullable | Sesión de validez de la identidad |
| `recording_id` | texto, nullable | Grabación de validez de la identidad |

La correspondencia de hablantes entre grabaciones debe sustentarse en las anotaciones originales. No se deduce simplemente del número de canal.

## 5. Procedencia y manifiesto

Las tablas normalizadas deben ser regenerables desde las fuentes identificadas en `fuentes.toml` y fijadas en `fuentes.lock.json`.

El manifiesto debe registrar, para cada salida:

- Versión del esquema normalizado.
- Fuente y distribución utilizadas.
- Identificadores y hashes de originales.
- Transformaciones aplicadas.
- Cantidad de filas y grabaciones generadas.
- Archivos resultantes e información necesaria para verificar su integridad.

Los registros de anomalías deben permitir cuantificar los casos que no pueden utilizarse directamente para evaluación.

**CALLHOME procesado (`talkbank/callhome`).** Los intervalos con inicios/finales finitos que incumplen `0 <= inicio < fin` se excluyen solamente de `diarizacion_segmentos.parquet`; la grabación, los demás segmentos y los originales se conservan. Se registra cada exclusión (archivo Parquet, fila e índice de intervalo de base cero, tiempos originales, etiqueta de hablante y motivo) en `muestra/normalizado/ANOMALIAS_CALLHOME.json`, dentro del directorio ignorado por Git. `MANIFIESTO_NORMALIZADO.json` conserva cantidad, ruta, política, origen y SHA-256 del informe, sin reproducir sus anotaciones. Las listas desalineadas, bytes de audio ausentes y tiempos no numéricos/no finitos siguen siendo errores de estructura y detienen la preparación; no se reparan inventando marcas.

**UBA Games Figshare v2.** En la comprobación del extremo temporal se admite únicamente para esta fuente un exceso de hasta `0,01 s`, coherente con la precisión centesimal observada en las anotaciones originales. La anotación y el exceso físico se conservan sin corregir el tiempo original: `anotacion_fuera_del_audio`, `exceso_terminal_max_s`, `exceso_aceptado_por_precision` y `exceso_superior_a_tolerancia` figuran en la tabla específica `uba_games_figshare/grabaciones.csv`. Su `procedencia.json` registra la tolerancia, grabaciones aceptadas por precisión y exceso máximo observado. Un par puede tener un exceso terminal físico y ser aceptado estructuralmente: **la tolerancia no extiende el audio ni habilita puntuar el tramo inexistente**. Una transformación posterior a RTTM deberá limitar explícitamente el extremo puntuable a la duración física, manteniendo las anotaciones originales inalteradas. La tolerancia no se aplica a CALLHOME ni a las demás fuentes.

Las tablas normalizadas no sustituyen a las tablas particulares ni a los datos originales: establecen una representación común trazable.

## 6. Validación estructural

La validación compartida comprobará:

- Existencia y unicidad de claves dentro de su ámbito.
- Integridad de las referencias entre grabaciones, segmentos y hablantes.
- Coherencia entre identidades, sesiones y agrupaciones.
- Validez numérica de duraciones e intervalos.
- Correspondencia entre límites temporales y duración de grabaciones.
- Valores permitidos para campos categóricos.
- Coherencia de la procedencia y los estados de disponibilidad.

Los datos problemáticos no deben desaparecer de las estadísticas de calidad. Cuando un registro no pueda normalizarse válidamente, la anomalía debe permanecer trazable a la fuente y contabilizarse en el EDA.

No se confunde validación estructural con viabilidad del producto.

## 7. Integración y responsabilidades

- `descargar_fuentes.py`: adquiere y verifica originales.
- `armar_muestra.py`: interpreta fuentes, genera derivados y construye las tablas normalizadas.
- Validación compartida: comprueba el cumplimiento de este contrato.
- `eda_viabilidad.ipynb`: calcula propiedades, riesgos y búsquedas de leakage, contrastándolos con los niveles a priori.
- `MANIFIESTO.json`: registra los artefactos y su procedencia.

Las conclusiones del EDA no se incorporan a los adaptadores ni se utilizan para modificar retrospectivamente los requisitos.

Este contrato cubre ASR y diarización. AMI, ICSI y los datos de minutas conservan sus estructuras existentes hasta que corresponda integrarlos sin introducir transformaciones innecesarias.

## 8. Aplicación incremental

El contrato se verifica mediante `scripts/validar_muestra.py`. El programa no modifica datos, no calcula conclusiones del EDA y admite validación independiente de ASR y diarización.

Desde la raíz del repositorio, una vez generadas las tablas normalizadas:

```bash
.venv/bin/python -I hito-2/scripts/validar_muestra.py --componente todos
```

Para comprobar únicamente un componente, utilizar `--componente asr` o `--componente diarizacion`. El parámetro `--raiz` permite indicar otro directorio de tablas; `--informe` permite guardar los resultados en JSON.

La ejecución devuelve código `0` cuando las tablas cumplen el contrato y código `1` si encuentra errores. Si aún no se generaron las tablas requeridas, informa su ausencia: no se considera una validación satisfactoria.

Primero se implementan y prueban los contratos compartidos con datos sintéticos.

Después se adaptan las fuentes existentes y las nuevas, conservando sus tablas originales.

Finalmente se integra el esquema normalizado en el notebook, se ejecuta el EDA y se decide la política definitiva de particiones según las búsquedas de leakage.

La creación de este documento no implica que las tablas normalizadas ya existan ni que las transformaciones hayan sido ejecutadas.

### Regeneración de la muestra normalizada

Con los originales adquiridos, fijados en `fuentes.lock.json` y las dependencias del entorno completo instaladas, ejecutar desde la raíz del repositorio:

```bash
.venv/bin/python -I hito-2/scripts/armar_muestra.py normalizado
```

Este comando reutiliza los adaptadores de OpenSLR, CORdeBA y UBA Games Figshare, incorpora Common Voice y CALLHOME, genera las cinco tablas normalizadas y comprueba su contrato antes de publicar los resultados.

Los archivos se escriben en `hito-2/muestra/normalizado/` y se registran en `MANIFIESTO_NORMALIZADO.json`. El manifiesto general conserva sus datos históricos e incorpora la procedencia de esta normalización.

Los derivados de trabajo se mantienen fuera de Git hasta verificar sus condiciones de redistribución. Esto no impide realizar el EDA local, pero todavía no constituye una muestra normalizada pública y autónoma.

Las referencias `audio_ref` identifican originales o derivados; no constituyen por sí mismas rutas directamente utilizables por un modelo. La decodificación, mezcla completa cuando corresponda y validación acústica son transformaciones pendientes de cierre.

La normalización conserva las particiones originales, pero no define `project_split`. Los grupos y duplicados deberán analizarse antes de congelar las particiones de evaluación.

El estado `validado_estructuralmente_no_evaluado` no acredita representatividad ni viabilidad del producto.