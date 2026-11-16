# Spec Delta

## Purpose

Congelar la muestra de evaluación de §2.3 de la definición de la PoC: obtener los originales verificados, elegir con semilla los clips, sesiones y reuniones, traducir AMI, normalizar el audio y fijar todo con SHA-256 en un manifiesto que cualquier integrante pueda verificar.

## ADDED Requirements

### Requirement: Originales verificados
Antes de seleccionar, `preparar` SHALL verificar cada original contra el hash fijado en `hito-2/fuentes.toml` o `hito-2/fuentes.lock.json`. Si falta un original o su hash no coincide, SHALL fallar nombrando el archivo, el hash esperado y el encontrado, sin escribir la muestra. No SHALL descargar nada por sí mismo: indica el comando del Hito 2 que lo obtiene.

#### Scenario: Original con hash distinto
- **WHEN** `wavs.rar` tiene un MD5 distinto del de `fuentes.toml`
- **THEN** `preparar` falla nombrando `wavs.rar` y los dos hashes, y no escribe el manifiesto

#### Scenario: Original ausente
- **WHEN** falta el archivo de Common Voice
- **THEN** `preparar` falla e indica `descargar_fuentes.py common_voice` y la variable `MDC_API_KEY`

### Requirement: Selección determinista
La selección SHALL depender solo de la semilla y de los originales: 3 clips de OpenSLR 61 y 2 del split `test` de Common Voice, de 5 personas distintas y de ambos géneros; 3 sesiones completas de Figshare con anotación completa, sin S26 a S30; 3 reuniones de AMI de series distintas, con al menos un ítem de acción y duración cerca de la mediana.

#### Scenario: Misma semilla, misma muestra
- **WHEN** se ejecuta `preparar` dos veces con la semilla 20261010 sobre los mismos originales
- **THEN** los dos manifiestos tienen el mismo contenido y el mismo `contenido_sha256`

#### Scenario: Sesiones excluidas
- **WHEN** se seleccionan las sesiones de Figshare
- **THEN** ninguna es S26, S27, S28, S29 ni S30, y el manifiesto registra el motivo de cada exclusión

#### Scenario: Clips de personas distintas
- **WHEN** se seleccionan los 5 clips
- **THEN** pertenecen a 5 hablantes distintos y hay al menos un clip de cada género

### Requirement: Traducción sintética de AMI
Los turnos y los ítems de minuta de las 3 reuniones SHALL traducirse con `Helsinki-NLP/opus-mt-en-es` en una revisión fija, sin muestreo. Cada texto traducido SHALL conservar su identificador, sus tiempos y su hablante de origen, y el manifiesto SHALL marcarlo como sintético con el modelo, la revisión y el texto original.

#### Scenario: Traducción repetible
- **WHEN** se traduce dos veces la misma reunión con la misma revisión del modelo
- **THEN** los textos traducidos son idénticos

#### Scenario: Marca de sintético
- **WHEN** se lee cualquier turno o ítem traducido de la muestra
- **THEN** su entrada en el manifiesto indica `sintetico: true`, el modelo y su revisión

### Requirement: Audio normalizado
Todo audio de la muestra SHALL quedar como WAV de 16 000 Hz, 1 canal y PCM de 16 bits, el formato de entrada de las Etapas 2 y 3. El manifiesto SHALL registrar para cada archivo el original, su hash y la transformación aplicada.

#### Scenario: Clip de OpenSLR
- **WHEN** se prepara un clip de OpenSLR 61, un WAV de 48 kHz dentro de `es_ar_female.zip`
- **THEN** queda un WAV de 16 kHz, mono y PCM16, y el manifiesto vincula su SHA-256 con el del WAV original

### Requirement: Manifiesto verificable
`preparar` SHALL escribir un manifiesto con la semilla, la versión del ejecutor, cada elemento con su fuente, original, transformación y SHA-256, y un `contenido_sha256` del conjunto. `preparar --verificar` SHALL comprobar los archivos contra el manifiesto sin modificarlos y fallar nombrando cada diferencia. Si ya hay una muestra congelada con otro `contenido_sha256`, `preparar` SHALL fallar sin reemplazar nada, salvo `--reemplazar`.

#### Scenario: Archivo alterado
- **WHEN** se modifica un WAV de la muestra después de congelarla
- **THEN** `preparar --verificar` falla nombrando ese archivo y los dos hashes

#### Scenario: Muestra intacta
- **WHEN** se ejecuta `preparar --verificar` sobre la muestra recién preparada
- **THEN** termina con código 0 y no modifica ningún archivo

#### Scenario: Muestra distinta de la congelada
- **WHEN** `preparar` produce un `contenido_sha256` distinto del manifiesto congelado
- **THEN** falla nombrando los dos hashes, sin reemplazar el manifiesto ni los datos
