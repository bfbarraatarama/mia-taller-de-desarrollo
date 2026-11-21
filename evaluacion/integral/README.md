# Evaluación integral del baseline

Procedimiento de calidad y latencia según la [sección 2.3 de la definición de la PoC](../../hito-3/definicion-de-la-poc.md#23-criterios-de-aceptación). El ejecutor utiliza la API de `src.pipeline`, sin modificar los módulos ni evaluar semánticamente las minutas.

## 1. Preparación

Desde la raíz del repositorio y con el [entorno de ejecución](../../README.md) instalado, disponer de FFmpeg, CUDA, PySide6, los pesos de pyannote `speaker-diarization-community-1` y Whisper `medium`, y Ollama local con `qwen2.5:7b` descargado. No descargar modelos durante las corridas. La configuración de minutas conserva los valores predeterminados de la aplicación, incluidas sus cinco secciones; se congela al preparar la muestra. No se permite un destino remoto.

La evaluación formal se realiza en la máquina de Matías (RTX 3050 Laptop de 6 GB y 31 GB de RAM). El modo `prueba` permite comprobar el procedimiento en otro equipo sin atribuir sus resultados al hardware objetivo. Registrar las condiciones de energía y carga y comprobar que el equipo y el código sean los mismos para las cinco corridas. Mantener libre la GPU de otros trabajos; no ejecutar corridas en paralelo ni cambiar las condiciones en mitad del protocolo.

### Reunión y referencia

- Seleccionar una reunión real en castellano, propia y consentida o externa con autorización de uso documentada, de al menos cinco minutos, idealmente de duración cercana a ese valor, con dos temas y una acción explícita con responsable. Conservar la entrada original del ejecutor. La fuente externa puede ser un fragmento continuo; registrar su procedencia, licencia e intervalo antes de las corridas.
- Antes del procesamiento, un integrante distinto del operador debe escuchar la grabación y elaborar las notas de referencia independientemente de los resultados del modelo. Incluir autor, fecha, los dos temas, la acción, su responsable y las marcas temporales que respaldan cada ítem. Registrar otras acciones si las hubiera, para no confundirlas con invenciones. Usar identidades autorizadas para las minutas.
- Para reuniones propias, obtener el consentimiento para grabación y procesamiento y la autorización de los participantes antes de publicar. Para las externas, documentar la autorización de uso y verificar que permita publicar los artefactos seleccionados. No publicar información privada.

Por ejemplo, en `resultados/evaluacion-integral/referencia.md` completar los campos con el contenido real:

```markdown
# Notas de referencia
Autor: [nombre]
Fecha: [fecha]

- Tema 1: [descripción y marcas temporales]
- Tema 2: [descripción y marcas temporales]
- Acción: [descripción, responsable y marcas temporales]
- Otras acciones explícitas, si las hubiera: [descripción y marcas temporales]
```

### Congelación de entradas

```bash
.venv/bin/python -m evaluacion.integral.evaluar preparar resultados/evaluacion-integral/baseline \
    --audio /ruta/reunion.wav \
    --notas resultados/evaluacion-integral/referencia.md \
    --autor 'NOMBRE DEL AUTOR' \
    --tipo formal \
    --equipo 'Máquina de Matías: RTX 3050 Laptop, 6 GB VRAM, 31 GB RAM' \
    --consentimiento
```

Para una fuente externa, reemplazar `--consentimiento` por `--procedencia /ruta/procedencia.json`. El JSON registra `titulo`, `url`, `url_metadatos`, `licencia`, `evidencia` (declaración documental de autorización), `seleccion` (procedimiento de selección y extracción), `sha256_original` (grabación completa), `sha256_fragmento` (WAV de entrada), `inicio_s` y `fin_s` (segundos enteros sobre la línea temporal de extracción). El fragmento debe ser WAV PCM16 mono de 16 kHz, con duración y hash coincidentes. La procedencia se conserva dentro del manifiesto; el ejecutor verifica su estructura y correspondencia con la entrada, no certifica derechos. El `sha256_original` del nivel superior del manifiesto mantiene su significado: hash del archivo de entrada al ejecutor, no de la grabación completa externa. Consultar la [muestra OSM LatAm](muestras/osm-latam-20220730/README.md).

Sustituir las rutas, nombres, tipo y equipo por los valores reales. Usar `--tipo prueba` y otro nombre de sesión para las comprobaciones de desarrollo. El comando normaliza mediante la ingesta existente a PCM16 mono de 16 kHz, guarda la fuente canónica y la divide por índices de muestras en tres WAV consecutivos, sin omitir ni duplicar contenido. Comprueba que la ingesta de los cortes tiene el mismo SHA-256 que el archivo único. El manifiesto conserva el hash de la grabación original, los hashes del audio canónico y las notas, los índices y hashes de los cortes y la configuración de minutas. El original previo a la normalización se conserva fuera de la sesión. La referencia no se incluye en ningún prompt. No modificar la muestra ni el manifiesto tras congelarlos.

## 2. Ejecución

```bash
.venv/bin/python -m evaluacion.integral.evaluar ejecutar resultados/evaluacion-integral/baseline \
    --operador 'NOMBRE DEL OPERADOR' \
    --condiciones 'DESCRIPCIÓN REAL DE LAS CONDICIONES DE EJECUCIÓN'
```

Cada corrida utiliza un directorio independiente, CUDA para diarización y STT, detección automática de hablantes y la configuración local de minutas congelada. Al llegar a la identificación se abre el diálogo existente de fichas. Escuchar los fragmentos, escribir los nombres que puedan identificarse y confirmar. No reutilizar automáticamente las etiquetas de otra corrida ni asignar nombres sin evidencia. El operador no puede ser el autor de las notas; la independencia efectiva depende de los integrantes.

| Corrida | Entrada | Calidad | Latencia |
|---|---|---|---|
| 01 | archivo único | sí | sí |
| 02 | archivos múltiples ordenados | sí | sí |
| 03 | archivo único | no | sí |
| 04 | archivos múltiples ordenados | no | sí |
| 05 | archivo único | no | sí |

La distribución mantiene ambas modalidades sobre el mismo contenido y fija las dos minutas de calidad antes de inferir. No pretende comparar estadísticamente las modalidades. El comando sin `--corrida` ejecuta las cinco en orden; `--corrida N` permite ejecutar individualmente una aún no iniciada. Ante una cancelación o fallo, conservar los artefactos y el registro, determinar la causa y no reemplazar la corrida silenciosamente. Las restantes pueden ejecutarse individualmente; una nueva serie completa requiere otra sesión. No reutilizar inferencias anteriores ni cambiar modelos para completar la serie. Si es necesario aplicar un plan B, documentar el cambio según la definición de la PoC y no presentar el resultado como una corrida del baseline original.

### Medición y trazabilidad

El reloj monotónico del ejecutor mide desde el pedido de preparación hasta el evento de finalización exitosa del workflow (minuta y estado publicados), descontando el tiempo dentro del diálogo de identificación. Incluye la preparación de fichas en el cliente y el costo de orquestación. El intervalo excluido comprende la interacción, reproducción y el procesamiento del propio diálogo durante su apertura; no mide de forma exacta el tiempo humano. Se conserva también la medición interna del workflow y el registro por etapa. La preparación experimental de la muestra, la inicialización de Qt y la recopilación de metadatos no se cuentan en la latencia.

Se registran la configuración, las versiones de paquetes de los checkpoints, los identificadores de modelos, el commit y el estado de cambios de Git, el sistema, FFmpeg, la GPU informada por `nvidia-smi` y las condiciones declaradas. Se consulta la versión, el digest y la residencia de Qwen en el servidor Ollama local antes y después de cada corrida. Se registra la revisión disponible en la caché de pyannote después de la ejecución; no acredita por sí sola la identidad de todos los pesos cargados. Para Whisper constan el modelo y la versión del paquete, no un hash independiente de sus pesos. Un dato no disponible queda como `null`, no se estima. Comprobar la comparabilidad de versiones y condiciones antes de considerar las cinco mediciones formales.

## 3. Evaluación de calidad y reporte

El autor de las notas completa `calidad.md` contrastando las minutas de las corridas 01 y 02 con sus notas y las marcas temporales, de acuerdo con la sección 2.3: dos temas, una acción con su responsable, ninguna acción inventada en ambas modalidades. Se admiten reformulaciones equivalentes. Registrar los ítems y su evidencia; no seleccionar retrospectivamente otras corridas ni utilizar un modelo como juez.

```bash
.venv/bin/python -m evaluacion.integral.evaluar reporte resultados/evaluacion-integral/baseline
```

El reporte genera `reporte.json` y `reporte.md` con estados y tiempos de las cinco corridas, el máximo y su contraste numérico con 1800 s. No vuelve a ejecutar modelos ni sustituye el juicio humano de `calidad.md`. Requiere cinco corridas completas para calcular el máximo de aceptación; los fallos y corridas pendientes permanecen visibles. La comprobación del nombre de GPU es informativa: confirmar además la máquina, su VRAM y RAM y la comparabilidad de condiciones. El umbral corresponde a cinco minutos de audio; no normalizar ni extrapolar el tiempo a partir de la duración efectiva. No se emite un veredicto global de la PoC.

Los directorios de trabajo conservan los artefactos originales de cada corrida, incluido el audio combinado, las copias de fuentes, los manifiestos y las salidas intermedias y finales. `medicion.json` contiene un registro derivado de los manifiestos, con configuración, fuentes ordenadas, tiempos, checkpoints y hashes, sin modificarlos. Para revisar los resultados sin repetir inferencias, se verifican los hashes de la muestra y de las salidas seleccionadas y los estados de las etapas. No invocar el reporte ni preparar la publicación mientras una corrida esté activa.

## 4. Publicación de evidencia autorizada

Una vez completado el juicio humano y revisados los resultados, preparar una copia explícita para publicación:

```bash
.venv/bin/python -m evaluacion.integral.evaluar reporte resultados/evaluacion-integral/baseline \
    --publicar evaluacion/integral/resultados/baseline
```

La copia conserva la muestra y sus cortes, las notas, la evaluación de calidad, las salidas seleccionadas, los registros derivados y el reporte regenerable. No incluye cinco copias del audio ni los manifiestos originales con rutas locales. Se conservan los hashes de estos últimos en los registros derivados y los originales en el área de trabajo. La selección no constituye una anonimización; revisar nombres, contenido, metadatos, condiciones y permisos antes de versionar. El comando no hace commit ni envía información a GitHub. Los directorios `resultados/` permanecen ignorados por defecto. Solo después de confirmar la autorización para publicar todo el contenido de la copia:

```bash
.venv/bin/python -m evaluacion.integral.evaluar reporte evaluacion/integral/resultados/baseline
git add -f -- evaluacion/integral/resultados/baseline
git diff --cached --stat
```

Para repetir las inferencias desde una copia publicada, usar la muestra congelada en una sesión nueva sin corridas previas, manteniendo el manifiesto, los cortes y la configuración original y registrando el contexto de ejecución. No declarar un consentimiento nuevo ni alterar los hashes de procedencia. El hash de la grabación anterior a la normalización se conserva como procedencia; la fuente canónica publicada es la entrada efectiva de las inferencias. No modificar la publicación anterior. Incorporar los resultados formales y sus limitaciones a [validación de la integración](../../docs/validacion-integracion.md).
