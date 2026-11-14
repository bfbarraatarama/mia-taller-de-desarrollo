# Spec Delta

## Purpose

Preparar de forma reproducible el dataset de test de diarización a partir de la sesión S26 de UBA Games (Figshare v2), empezando por la grabación `s26.objects.04`. Se usan los WAV estéreo completos convertidos a mono, con referencias de dos hablantes validadas, para medir el DER y el JER de la Etapa 2 sin alterar los originales.

## ADDED Requirements

### Requirement: Verificación de los originales
Antes de leer su contenido, el sistema SHALL verificar que `phrases.rar` y `wavs.rar` coincidan en tamaño y MD5 con `hito-2/fuentes.toml` y en SHA-256 con `hito-2/fuentes.lock.json`. Si alguno no coincide o falta, SHALL fallar sin escribir ningún derivado.

#### Scenario: Originales correctos
- **WHEN** los dos RAR de la caché del Hito 2 coinciden con el registro y el lock
- **THEN** la preparación continúa con la verificación de los archivos extraídos

#### Scenario: Original alterado
- **WHEN** el SHA-256 de `wavs.rar` no coincide con `fuentes.lock.json`
- **THEN** la preparación falla nombrando el archivo y no escribe audios, referencias ni manifiesto

### Requirement: Archivos extraídos verificados contra el RAR
El sistema SHALL leer el audio y las anotaciones de `hito-2/.cache/uba_games/figshare-v2/extraidos/`, y antes de usarlos SHALL verificar cada archivo contra la entrada del RAR que le corresponde (ruta, tamaño y CRC32), según el listado de 7-Zip, sin extraer nada. Un archivo ausente, distinto o con una ruta interna absoluta o con `..` SHALL hacer fallar la preparación. Los originales SHALL quedar sin cambios.

#### Scenario: Extraídos íntegros
- **WHEN** el WAV completo y las dos anotaciones de `s26.objects.04` coinciden en tamaño y CRC32 con sus entradas en `wavs.rar` y `phrases.rar`
- **THEN** la preparación continúa, y el manifiesto registra la ruta, el tamaño, el CRC32 y el SHA-256 de cada archivo usado

#### Scenario: Extraído alterado
- **WHEN** un archivo de `extraidos/` tiene un CRC32 distinto del de su entrada en el RAR
- **THEN** la preparación falla nombrando el archivo, sin escribir derivados

#### Scenario: Originales intactos
- **WHEN** termina una preparación
- **THEN** el SHA-256 de los dos RAR y de los archivos extraídos usados es igual al de antes de empezar

#### Scenario: 7-Zip ausente en Windows
- **WHEN** se ejecuta la preparación en Windows sin 7-Zip en `PATH` ni en su carpeta de instalación habitual
- **THEN** la preparación falla con un mensaje que indica cómo instalar 7-Zip o cómo indicar su ruta

### Requirement: Sesión y grabaciones del dataset
El sistema SHALL usar la sesión S26. Como audio de entrada usa el WAV estéreo completo de cada tarea, de `wavs/Sin separar canales/S26_falta_separar_canales/s26.objects.<TT>.wav`, y como referencia `phrases/S26/s26.objects.<TT>.channel1.phrases` y `.channel2.phrases`. Los WAV separados por canal (`wavs/S26/*.channelN.wav`) SHALL NOT usarse como entrada del modelo. La primera evaluación SHALL limitarse a `s26.objects.04`.

#### Scenario: Primera evaluación
- **WHEN** se prepara el dataset con la selección inicial
- **THEN** el manifiesto incluye solo `figshare_v2_S26_objects_04`, con su WAV estéreo completo y sus dos anotaciones

#### Scenario: Canales separados no usados como entrada
- **WHEN** existe `wavs/S26/s26.objects.04.channel1.wav`
- **THEN** no se usa como entrada del modelo; como mucho, se registra en el manifiesto como auxiliar

#### Scenario: Ampliación a la sesión
- **WHEN** se autoriza ampliar la selección a todas las tareas de S26
- **THEN** el manifiesto lista cada grabación de S26 con WAV completo y anotaciones, válida o excluida con su motivo, y ninguna de otra sesión

### Requirement: Criterios de validez de una grabación
El sistema SHALL exigir: el WAV completo de 16 kHz, 2 canales y PCM16, legible completo; la anotación de los dos canales, bien formada; un exceso terminal de cada anotación sobre la duración del WAV de 0,01 s o menos; y la correspondencia canal ↔ hablante. Una grabación que no cumple SHALL excluirse y registrarse con el motivo.

#### Scenario: Grabación válida
- **WHEN** `s26.objects.04.wav` es estéreo de 16 kHz y PCM16 de 52,271 s, y sus dos anotaciones terminan 0,0092 s después
- **THEN** se preparan su WAV mono y su referencia

#### Scenario: Anotación de un canal faltante
- **WHEN** una tarea tiene WAV completo y la anotación del canal 1, pero no la del canal 2
- **THEN** la grabación no se prepara y el manifiesto la registra como excluida con el motivo "canal 2 sin anotación"

#### Scenario: Exceso fuera de tolerancia
- **WHEN** una anotación termina 0,3 s después del final del WAV completo
- **THEN** la grabación se excluye con el motivo y el exceso medido

#### Scenario: WAV que no es estéreo
- **WHEN** el WAV completo de una tarea tiene 1 canal o una frecuencia distinta de 16 kHz
- **THEN** la grabación se excluye con el motivo y los valores encontrados

### Requirement: Correspondencia canal ↔ hablante
Cada canal del WAV completo SHALL correlacionarse más con su WAV separado que con el otro, y la correlación SHALL registrarse. Los WAV separados SHALL tener los mismos cuadros que el completo o, como mucho, 1 cuadro más al final (decisión del 08/11/2026). La correlación se calcula sobre los cuadros en común y la diferencia se registra.

#### Scenario: WAV separado con un cuadro de más al final
- **WHEN** `s26.objects.06.channel1.wav` tiene 501 970 cuadros y el WAV completo 501 969, alineados en desfase 0
- **THEN** la correspondencia se comprueba sobre los 501 969 cuadros en común, el manifiesto registra `diferencia_cuadros: 1` y la grabación no se excluye por eso

#### Scenario: WAV separado con otra diferencia de cuadros
- **WHEN** un WAV separado tiene 2 cuadros más o 1 cuadro menos que el WAV completo
- **THEN** la grabación se excluye con el motivo y los cuadros de cada archivo

#### Scenario: Canales invertidos
- **WHEN** `channel1.wav` se correlaciona más con el canal derecho del WAV completo que con el izquierdo
- **THEN** la grabación se excluye con el motivo "canales invertidos o mal asignados"

### Requirement: Validación de las anotaciones originales
El sistema SHALL rechazar una anotación mal formada según los criterios del Hito 2: línea sin tres campos separados por tabulador, texto vacío, tiempos no finitos, `start < 0` o `start >= end`, o un inicio anterior al fin previo en más de 0,0001 s. La grabación SHALL excluirse con el número de línea.

#### Scenario: Línea mal formada
- **WHEN** una anotación tiene una línea con dos campos
- **THEN** la grabación se excluye y el motivo indica el archivo y el número de línea

### Requirement: Conversión del WAV estéreo a mono
Por cada grabación válida, el sistema SHALL leer el WAV estéreo original sin modificarlo y escribir un WAV derivado de 16 kHz, mono y PCM16, con la misma cantidad de cuadros. Lo SHALL hacer combinando los dos canales como el Hito 2: suma de muestras y división entera por 2. El WAV derivado SHALL ser una entrada válida de la Etapa 2 y es el que recibe pyannote.

#### Scenario: Conversión de s26.objects.04
- **WHEN** se convierte `s26.objects.04.wav` (836 333 cuadros, 2 canales)
- **THEN** el WAV derivado tiene 836 333 cuadros, 1 canal, 16 kHz y PCM16, pasa la validación de entrada de la Etapa 2, y cada muestra es `(izquierda + derecha) // 2`

#### Scenario: Conversión determinista
- **WHEN** se convierte dos veces el mismo WAV estéreo
- **THEN** los dos WAV mono tienen el mismo SHA-256, y el WAV estéreo original conserva el suyo

### Requirement: Indicador de cobertura de la anotación
Antes de interpretar las métricas, el sistema SHALL calcular por canal un indicador de cobertura que compare la energía del canal correspondiente del WAV estéreo con los intervalos anotados como habla y como `#`. SHALL registrar cuánto tiempo con energía alta queda marcado `#` y cuánto anotado como habla tiene energía baja. El indicador SHALL presentarse como indicio, no como prueba de que falte habla.

#### Scenario: Posible habla sin anotar
- **WHEN** un canal tiene 3 s con energía por encima del umbral dentro de intervalos `#`
- **THEN** el reporte registra 3 s de posible habla sin anotar en ese canal, con sus intervalos, y lo marca como indicio a revisar, sin cambiar la referencia

#### Scenario: Cobertura sin indicios
- **WHEN** la energía alta de un canal cae dentro de intervalos anotados como habla
- **THEN** el reporte registra 0 s de posible habla sin anotar para ese canal

### Requirement: Política de etiquetas de la referencia
El sistema SHALL convertir cada intervalo anotado en habla del participante de su canal, salvo `#` (silencio marcado), que SHALL excluirse. Toda otra etiqueta sin letras SHALL clasificarse en una política versionada como `habla` o `excluir`; una etiqueta sin clasificar SHALL hacer fallar la preparación y listarse.

#### Scenario: Silencio marcado
- **WHEN** un canal tiene un intervalo con texto `#`
- **THEN** ese intervalo no aparece en la referencia y el manifiesto lo cuenta como excluido por `#`

#### Scenario: Etiqueta especial sin clasificar
- **WHEN** aparece un intervalo cuyo texto no tiene letras y no está en la política
- **THEN** la preparación falla y lista cada etiqueta sin clasificar con su cantidad de apariciones

#### Scenario: Etiquetas de S26 clasificadas
- **WHEN** se prepara S26 completo con la política del 08/11/2026, que clasifica `-?` y `?-` como `habla`
- **THEN** los intervalos `-?` de las tareas 09 y 18 y `?-` de la tarea 12 entran en la referencia como habla del participante de su canal, y el manifiesto registra el SHA-256 de esa política

#### Scenario: Etiqueta clasificada como excluir
- **WHEN** la política clasifica una etiqueta como `excluir`
- **THEN** sus intervalos no aparecen en la referencia y el manifiesto los cuenta por etiqueta

### Requirement: Hablantes y solapamientos de la referencia
El sistema SHALL etiquetar a cada participante como `figshare_v2_<sesion>_canal<n>`. Los intervalos superpuestos o contiguos del mismo canal SHALL unirse en uno. Los intervalos de canales distintos que se superponen SHALL conservarse como habla superpuesta.

#### Scenario: Solapamiento entre participantes
- **WHEN** los dos canales tienen habla en el mismo intervalo
- **THEN** la referencia contiene un segmento de cada participante en ese intervalo

#### Scenario: Intervalos del mismo canal superpuestos
- **WHEN** dos intervalos del canal 1 se superponen en 0,00005 s
- **THEN** la referencia contiene un único segmento del canal 1 que cubre ambos, y el manifiesto cuenta una unión

### Requirement: Tolerancia temporal de la referencia
El sistema SHALL usar la tolerancia de fin del Hito 2, de 0,01 s. Un intervalo que termina después de la duración real de la mezcla por 0,01 s o menos SHALL ajustarse a esa duración en la referencia de evaluación. La anotación original SHALL NOT modificarse, y el manifiesto SHALL conservar, por cada ajuste, el canal, la línea, el fin original y el fin ajustado.

#### Scenario: Exceso dentro de la tolerancia
- **WHEN** el último intervalo de un canal termina 0,004 s después del final de la mezcla
- **THEN** la referencia lo termina en la duración de la mezcla, y el manifiesto registra ese ajuste con el fin original y el ajustado

#### Scenario: Tiempos originales conservados
- **WHEN** se compara el manifiesto con la anotación original después de una preparación con ajustes
- **THEN** cada fin original registrado coincide con el de la línea de la anotación, y la anotación de `extraidos/` y la del RAR siguen siendo las mismas

### Requirement: Validación de la referencia antes del DER
Antes de calcular las métricas de calidad, el sistema SHALL validar cada referencia: segmentos con `0 <= start < end <= duración`, hablante no vacío, sin duplicados y al menos un segmento de habla. Si no es utilizable, SHALL registrar como nulas todas las métricas de calidad de esa grabación (DER, JER y sus componentes), con el motivo, y SHALL NOT informar ningún valor.

#### Scenario: Referencia utilizable
- **WHEN** una referencia cumple todas las condiciones
- **THEN** se calculan el DER y el JER de esa grabación

#### Scenario: Referencia sin habla
- **WHEN** todos los intervalos de una grabación son `#`
- **THEN** el reporte registra `der_estricto: null`, `der_tolerancia: null` y `jer: null` con el motivo "referencia sin habla"

### Requirement: Cálculo y registro del DER
El sistema SHALL calcular dos métricas por grabación y por sesión, con habla superpuesta: `der_estricto`, sin tolerancia en los bordes, y `der_tolerancia`, con la tolerancia NIST de ±0,25 s por borde. Cada una SHALL registrar su nombre, collar total, tolerancia por lado, herramienta y versión, solapamiento y componentes, sin umbral. SHALL NOT presentarse como un valor de `md-eval`.

#### Scenario: Dos métricas por sesión
- **WHEN** se evalúa una sesión con varias grabaciones utilizables
- **THEN** el reporte tiene `der_estricto` y `der_tolerancia` de cada grabación y acumulados de la sesión, cada uno con su collar total, su tolerancia por lado, `incluye_solapamiento: true` y los componentes (falsa alarma, habla perdida, confusión)

#### Scenario: Métricas distinguibles
- **WHEN** se lee el reporte de una grabación
- **THEN** `der_estricto` registra un collar total de 0 s y una tolerancia por lado de 0 s, `der_tolerancia` registra un collar total de 0,5 s y una tolerancia por lado de 0,25 s, las dos indican `pyannote.metrics` y su versión como herramienta, y no hay ningún campo `der` ambiguo

#### Scenario: Borde dentro de la tolerancia NIST
- **WHEN** la hipótesis difiere de la referencia solo en un borde desplazado 0,2 s
- **THEN** `der_estricto` es mayor que 0 y `der_tolerancia` es 0

#### Scenario: Borde fuera de la tolerancia NIST
- **WHEN** la hipótesis difiere de la referencia solo en un borde desplazado 0,4 s
- **THEN** `der_estricto` y `der_tolerancia` son mayores que 0, y `der_tolerancia` es menor que `der_estricto`

#### Scenario: El collar solo afecta a la métrica con tolerancia
- **WHEN** la hipótesis difiere de la referencia solo en un borde desplazado 0,05 s
- **THEN** `der_estricto` es mayor que 0 y `der_tolerancia` es 0

### Requirement: Cálculo y registro del JER
El sistema SHALL calcular el JER (Jaccard Error Rate) por grabación y por sesión, sin collar y con el habla superpuesta, con `pyannote.metrics`. SHALL registrarlo como `jer` junto con su collar, si incluye solapamiento, la herramienta y su versión, y el error por hablante de la referencia, sin umbral.

#### Scenario: JER por sesión
- **WHEN** se evalúa una sesión con varias grabaciones utilizables
- **THEN** el reporte tiene `jer` de cada grabación y acumulado de la sesión, con `collar_pyannote_s: 0.0`, `incluye_solapamiento: true`, la herramienta y el error de cada hablante de la referencia

#### Scenario: JER de una hipótesis perfecta
- **WHEN** la hipótesis coincide exactamente con la referencia
- **THEN** `jer` es 0

### Requirement: Componentes y dispersión del error
Para cada métrica de DER, el sistema SHALL registrar la falsa alarma, la habla perdida y la confusión, en segundos y como proporción del habla de la referencia. Para DER y JER SHALL informar el valor acumulado de lo evaluado, ponderado por el tiempo, y, cuando haya dos grabaciones o más, la mediana, el rango intercuartil y la peor grabación.

#### Scenario: Componentes del DER
- **WHEN** se evalúa una grabación utilizable
- **THEN** cada bloque de DER trae `falsa_alarma_s`, `habla_perdida_s`, `confusion_s`, `total_referencia_s` y la proporción de cada componente sobre `total_referencia_s`

#### Scenario: Dispersión por grabación
- **WHEN** se evalúan varias grabaciones de S26
- **THEN** el reporte total trae, para `der_estricto`, `der_tolerancia` y `jer`, el valor acumulado, la mediana, el primer y el tercer cuartil, y la grabación con el valor más alto

#### Scenario: Estadísticos por grabación y ranking
- **WHEN** se evalúan varias grabaciones
- **THEN** el reporte total trae, para cada métrica, la media, la mediana, los cuartiles, el mínimo, el máximo, la desviación estándar muestral y la mejor y la peor grabación, sin ponderar, separados del acumulado ponderado por el tiempo; y una tabla por grabación ordenada por `der_estricto`

#### Scenario: Error con y sin solapamiento
- **WHEN** se evalúa una grabación utilizable
- **THEN** el reporte separa los componentes del `der_estricto` en la región con 2 hablantes o más en la referencia y en el resto de la grabación, con el emparejamiento global fijo, de modo que las dos regiones suman los componentes de la grabación; y registra la duración del audio, el habla de la referencia y el habla superpuesta

#### Scenario: Tiempo evaluado con tolerancia NIST
- **WHEN** se calcula `der_tolerancia`
- **THEN** el reporte registra, por grabación y acumulado, el habla de referencia evaluada con y sin collar y la proporción evaluada

#### Scenario: Una sola grabación
- **WHEN** se evalúa solo `s26.objects.04`
- **THEN** el reporte trae sus valores y deja la dispersión en `null`, con el motivo "una sola grabación"

### Requirement: Cantidad de hablantes
El sistema SHALL registrar, por grabación, la cantidad de hablantes de la referencia y la detectada por la corrida principal, y la proporción de grabaciones en que coinciden, sin umbral.

#### Scenario: Cantidad que no coincide
- **WHEN** en una grabación con 2 hablantes en la referencia la corrida principal detecta 3
- **THEN** el reporte registra `hablantes_referencia: 2`, `hablantes_detectados: 3` y `cantidad_coincide: false`, y la proporción total de coincidencias la cuenta como no coincidente

### Requirement: Corrida principal y corrida diagnóstica
El sistema SHALL diarizar cada grabación en una corrida principal sin `num_speakers`. Además SHALL permitir una corrida diagnóstica con `num_speakers` igual a la cantidad de hablantes de la referencia (2), que se ejecuta solo cuando se pide, y SHALL calcular las métricas de cada corrida por separado. La corrida diagnóstica SHALL NOT presentarse como el resultado del producto.

#### Scenario: Primera evaluación solo con la corrida principal
- **WHEN** se evalúa `s26.objects.04` sin pedir la corrida diagnóstica
- **THEN** el reporte tiene solo el bloque `principal` (`num_speakers: null`), y `diagnostico_num_speakers` en `null` con el motivo "no solicitada"

#### Scenario: Dos corridas identificadas
- **WHEN** se evalúa una grabación utilizable pidiendo la corrida diagnóstica
- **THEN** el reporte tiene un bloque `principal` (`num_speakers: null`) y uno `diagnostico_num_speakers` (`num_speakers: 2`), cada uno con su DER, su JER, sus componentes y la cantidad de hablantes detectada

#### Scenario: Separar el error de cantidad
- **WHEN** la corrida principal no detecta la cantidad correcta de hablantes en una grabación
- **THEN** el reporte permite comparar su DER y su JER con los de la corrida diagnóstica de la misma grabación

### Requirement: Dispositivo de la evaluación de calidad
La evaluación de calidad SHALL poder ejecutarse en CPU o en GPU con el mismo código, y SHALL registrar el dispositivo usado y el tiempo de cada corrida. Las comprobaciones propias de CUDA (memoria y `dispositivo: cuda`) SHALL quedar en una prueba aparte, que solo se ejecuta con CUDA.

#### Scenario: Reutilización de una corrida compatible
- **WHEN** ya existe una corrida de una grabación con el par JSON/meta consistente, el mismo WAV mono (SHA-256), el mismo modelo, las mismas versiones de torch y pyannote.audio, el mismo `num_speakers` y el mismo dispositivo
- **THEN** la evaluación la reutiliza sin diarizar otra vez, el reporte marca `reutilizada: true` con el motivo, y `--rehacer` obliga a diarizar

#### Scenario: Evaluación en CPU
- **WHEN** se ejecuta la evaluación de calidad en una máquina sin GPU
- **THEN** se calculan todas las métricas de calidad, el reporte registra `dispositivo: cpu`, y las comprobaciones de memoria de CUDA se saltean con su motivo

### Requirement: Declaración de las limitaciones de la referencia
El reporte de calidad SHALL declarar las limitaciones de la referencia: anotación de frases transcritas por canal y no de turnos; sin medida de acuerdo entre anotadores; 2 hablantes por sesión; dominio de juego, no de reunión; y transcripción de S26 posiblemente incompleta, según el README de origen, junto con el resultado del indicador de cobertura. SHALL indicar que las métricas no tienen umbral y son una línea de base.

#### Scenario: Limitaciones en el reporte
- **WHEN** se escribe el reporte total de calidad
- **THEN** incluye un bloque `limitaciones` con esas cinco condiciones, el resultado del indicador de cobertura y la indicación de que los valores son una línea de base sin umbral

### Requirement: Procedencia y reproducibilidad
El sistema SHALL escribir un manifiesto versionable con dos secciones. `contenido` tiene solo datos deterministas: originales, política, tolerancias y selección de grabaciones; y, por grabación, estado, motivo, archivos usados (con ruta, tamaño, CRC32 y SHA-256), conteos, ajustes, indicador de cobertura y SHA-256 del WAV mono y de la referencia. `ejecucion` tiene los metadatos variables. Con los mismos originales, política y tolerancias, `contenido` SHALL ser idéntico byte a byte.

#### Scenario: Preparación repetida
- **WHEN** se prepara el dataset dos veces con los mismos originales, la misma política y las mismas tolerancias, en Windows o en Linux
- **THEN** la sección `contenido` de los dos manifiestos, serializada en forma canónica, es idéntica byte a byte, y su SHA-256 coincide

#### Scenario: Metadatos variables
- **WHEN** las dos preparaciones se hacen en fechas, máquinas o con versiones de 7-Zip o de Python distintas
- **THEN** solo difiere la sección `ejecucion`, y la verificación de reproducibilidad no la compara

#### Scenario: Cambio de política
- **WHEN** se cambia la clasificación de una etiqueta en `politica_etiquetas.json` y se prepara otra vez
- **THEN** la sección `contenido` cambia, incluido el SHA-256 de la política que registra

#### Scenario: Verificación de un dataset preparado
- **WHEN** se verifica un dataset ya preparado contra su manifiesto y una mezcla fue modificada
- **THEN** la verificación falla nombrando la grabación afectada

### Requirement: Derivados fuera del control de versiones
Las mezclas y las referencias SHALL escribirse en una carpeta excluida de git. El manifiesto SHALL NOT contener el texto de las anotaciones.

#### Scenario: Nada de audio en git
- **WHEN** termina una preparación
- **THEN** `git status` muestra a lo sumo el manifiesto, y ninguna mezcla ni referencia
