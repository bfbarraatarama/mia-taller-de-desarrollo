# Spec Delta

## Purpose

Unir `diarization.json` (Etapa 2) y `asr.json` (Etapa 3) sobre el mismo `audio.wav` en una transcripción por intervención, con hablante, nombre, texto, tiempos y marcas de confianza, que la Etapa 5 consume sin transformaciones.

## ADDED Requirements

### Requirement: Validación del audio de entrada
Antes de leer los JSON, el sistema SHALL verificar que `audio.wav` exista y sea un WAV de 16 000 Hz, 1 canal y PCM de 16 bits, y SHALL tomar su duración de la cabecera. Si no cumple, SHALL fallar indicando la condición, el valor esperado y el encontrado.

#### Scenario: Audio normalizado
- **WHEN** se procesa un WAV de 16 kHz, mono y PCM16 grabado con la interfaz de la Etapa 1
- **THEN** la validación pasa y la duración usada es la de su cabecera

#### Scenario: Audio no normalizado
- **WHEN** se indica un WAV estéreo de 48 kHz
- **THEN** la ejecución falla con un mensaje que nombra los canales y la frecuencia esperados y encontrados

### Requirement: Validación de diarization.json
El sistema SHALL aplicar las mismas reglas que `validar_diarizacion` de la Etapa 2, sin tolerancia en los tiempos: raíz con solo `segments`; cada segmento con exactamente `start`, `end` y `speaker`; tiempos numéricos finitos con `0 <= start < end <= duración`; `speaker` texto no vacío; segmentos ordenados por `start`. Ante una violación SHALL fallar nombrando el archivo, el índice y la regla.

#### Scenario: Diarización de la Etapa 2
- **WHEN** se valida cualquiera de los 25 `diarization.json` de S26 publicados por la Etapa 2
- **THEN** el resultado coincide con el de `validar_diarizacion` de la Etapa 2 sobre el mismo archivo

#### Scenario: Segmento después del audio
- **WHEN** un segmento de `diarization.json` termina 0,01 s después de la duración del audio
- **THEN** la ejecución falla nombrando `diarization.json`, el índice del segmento y la regla `end <= duración`

### Requirement: Validación de asr.json
El sistema SHALL aplicar las reglas de `validate_asr_contract` de la Etapa 3: `language` texto no vacío; `segments` lista; cada segmento con `start` y `end` finitos, no negativos, con `start < end`, `text` no vacío y `words` lista, posiblemente vacía; cada palabra con `word` no vacío y tiempos con las mismas reglas. Los fines SHALL admitirse hasta 1,0 s después de la duración del audio. Ante otra violación SHALL fallar nombrando el archivo, el índice y la regla.

#### Scenario: Fin dentro del margen de la Etapa 3
- **WHEN** el último segmento de `asr.json` y su última palabra terminan 0,4 s después de la duración del audio
- **THEN** la ejecución continúa, ambos se recortan a la duración y el recorte queda contado en `transcription.meta.json`

#### Scenario: Palabra que queda vacía tras el recorte
- **WHEN** una palabra empieza después de la duración del audio y termina dentro del margen de 1,0 s
- **THEN** la palabra se descarta y queda contada en `transcription.meta.json`

#### Scenario: Fin fuera del margen de la Etapa 3
- **WHEN** un segmento de `asr.json` termina 1,5 s después de la duración del audio
- **THEN** la ejecución falla nombrando `asr.json`, el índice del segmento y el margen de 1,0 s

#### Scenario: Segmento sin palabras
- **WHEN** un segmento de `asr.json` tiene `words: []`
- **THEN** la validación pasa

### Requirement: Estructura de transcription.json
El sistema SHALL escribir `transcription.json` con raíz `{"segments": [...]}` y cada intervención con exactamente `start`, `end`, `speaker`, `name`, `text`, `overlap` y `ambiguous`, sin otros campos.

#### Scenario: Campos exactos
- **WHEN** se procesan una diarización y una transcripción válidas con al menos una palabra
- **THEN** la raíz tiene solo `segments` y cada intervención tiene exactamente los 7 campos

#### Scenario: Lectura por la Etapa 5
- **WHEN** la Etapa 5 lee el `transcription.json` producido con `leer_transcripcion` de `src/minutas/entrada.py`
- **THEN** lo acepta sin errores

### Requirement: Valores de las intervenciones
Cada intervención SHALL cumplir: tiempos redondeados a 3 decimales con `0 <= start < end <= duración`; orden por `start`; `speaker` una etiqueta presente en `diarization.json` o `null`; `name` texto no vacío o `null`; `text` no vacío y sin espacios en los extremos; `overlap` y `ambiguous` booleanos.

#### Scenario: Salida dentro del contrato
- **WHEN** se procesan una diarización y una transcripción válidas con al menos una palabra
- **THEN** cada intervención cumple todas las reglas de valores

#### Scenario: Redondeo y texto
- **WHEN** la primera palabra de una intervención empieza en 1,23456 s y su texto llega como `" hola"`
- **THEN** la intervención tiene `start: 1.235` y su texto empieza con `hola`, sin espacio inicial

### Requirement: Validación de la propia salida
Antes de escribir, el sistema SHALL validar `transcription.json` contra su estructura y sus valores. Si no cumple, SHALL fallar sin escribirlo.

#### Scenario: Salida inválida detectada
- **WHEN** por un error interno se arma una intervención con `end <= start`
- **THEN** la ejecución falla nombrando la intervención y la regla, y no se escribe `transcription.json`

### Requirement: Metadatos de la ejecución
Junto a `transcription.json`, el sistema SHALL escribir `transcription.meta.json` con: versión del módulo, fecha, SHA-256 de `audio.wav`, `diarization.json`, `asr.json` y `transcription.json`, umbrales usados, si hubo etiquetado, tiempos y palabras recortados o descartados en la validación, y conteos de palabras sin hablante e intervenciones con `overlap` y con `ambiguous`.

#### Scenario: Metadatos coherentes con el resultado
- **WHEN** termina una ejecución exitosa
- **THEN** el SHA-256 de `transcription.json` registrado en el meta coincide con el del archivo escrito, y los SHA-256 de las entradas coinciden con los de los archivos usados

### Requirement: Asociación de palabras e intervenciones
El sistema SHALL asignar a cada palabra de `asr.json` un hablante de `diarization.json` según la regla de `design.md` y SHALL formar intervenciones con palabras consecutivas del mismo hablante. El texto de cada intervención SHALL ser la concatenación de sus palabras en orden.

#### Scenario: Happy path con dos hablantes
- **WHEN** dos hablantes alternan turnos sin superponerse y cada palabra cae dentro de un turno
- **THEN** cada intervención tiene el `speaker` del turno de sus palabras, `overlap: false` y `ambiguous: false`, y la concatenación de los textos de todas las intervenciones contiene todas las palabras de `asr.json` en orden


#### Scenario: Ejemplo ideal
- **WHEN** se procesa el ejemplo ideal de D10 (`design.md`)
- **THEN** el 100 % de las palabras tiene el hablante de `referencia.json` y todas las intervenciones tienen `overlap: false` y `ambiguous: false`
### Requirement: Habla superpuesta y hablante dudoso (2.1.2)
El sistema SHALL conservar todas las palabras aunque caigan en tramos con dos o más hablantes. SHALL marcar `overlap: true` si la intervención tiene 0,2 s o más con dos o más hablantes activos. SHALL marcar `ambiguous: true` si `speaker` es `null`, si otra etiqueta cubre el 30 % o más de su duración, o si los turnos de su propia etiqueta cubren menos del 50 %. Los cálculos SHALL hacerse en milisegundos enteros.

#### Scenario: Dos personas hablan a la vez
- **WHEN** una intervención cae en un tramo donde `SPEAKER_00` y `SPEAKER_01` tienen turnos simultáneos durante 1,5 s
- **THEN** la intervención tiene `overlap: true` y su texto se conserva completo

#### Scenario: Interrupción breve
- **WHEN** en una intervención de 12 s de `SPEAKER_00`, cubierta entera por su turno, `SPEAKER_01` tiene un turno de 0,3 s
- **THEN** la intervención tiene `overlap: true` y `ambiguous: false`

#### Scenario: Roce de bordes
- **WHEN** el turno de `SPEAKER_01` empieza 0,05 s antes de que termine la intervención de `SPEAKER_00`
- **THEN** la intervención tiene `overlap: false`

#### Scenario: Segundo hablante en el 30 %
- **WHEN** en una intervención de 10,0 s de `SPEAKER_00`, `SPEAKER_01` tiene turnos que cubren 3,0 s
- **THEN** la intervención tiene `ambiguous: true`

#### Scenario: Texto sin respaldo en la diarización
- **WHEN** una intervención de 2,0 s de `SPEAKER_00` tiene solo 0,8 s cubiertos por turnos de `SPEAKER_00`
- **THEN** la intervención tiene `ambiguous: true`

#### Scenario: Valores límite
- **WHEN** una intervención tiene exactamente 0,200 s con dos hablantes, otra etiqueta cubre 29,9 % y su propia etiqueta cubre exactamente el 50,0 %
- **THEN** tiene `overlap: true` y `ambiguous: false`

#### Scenario: Sin hablante
- **WHEN** una intervención tiene `speaker: null`
- **THEN** tiene `ambiguous: true`

### Requirement: Cualquier cantidad de hablantes (2.1.3)
El sistema SHALL procesar diarizaciones con cualquier cantidad de etiquetas, sin límite fijo.

#### Scenario: Seis o más hablantes
- **WHEN** `diarization.json` tiene 8 etiquetas distintas
- **THEN** `transcription.json` puede contener las 8 etiquetas y el etiquetado ofrece 8 fichas

### Requirement: Entradas sin habla (2.1.4)
Si `asr.json` no tiene ninguna palabra ni segmento con texto, el sistema SHALL fallar con el motivo «sin habla transcrita». Si `diarization.json` no tiene segmentos y `asr.json` tiene texto, el sistema SHALL escribir `transcription.json` con todas las intervenciones con `speaker: null`, `name: null` y `ambiguous: true`, y SHALL saltear el etiquetado.

#### Scenario: Sin habla transcrita
- **WHEN** `asr.json` tiene `segments: []`
- **THEN** la ejecución falla con el motivo «sin habla transcrita» y no se escribe `transcription.json`

#### Scenario: Diarización vacía con texto
- **WHEN** `diarization.json` tiene `segments: []` y `asr.json` tiene texto
- **THEN** `transcription.json` conserva todo el texto, con `speaker: null` y `ambiguous: true` en cada intervención, y no se muestran fichas

### Requirement: Conservación del último resultado válido ante un fallo
Si una ejecución falla, el sistema SHALL NOT sobrescribir ni eliminar `transcription.json`, `transcription.meta.json` ni `speakers.json` previos, y SHALL NOT dejar archivos parciales con esos nombres. Los resultados SHALL escribirse en archivos temporales y reemplazarse con `os.replace` solo al terminar bien. Las entradas SHALL quedar intactas.

#### Scenario: Falla con un resultado anterior
- **WHEN** existe un resultado válido anterior y una nueva ejecución falla al validar sus entradas
- **THEN** `transcription.json`, `transcription.meta.json` y `speakers.json` quedan byte a byte iguales a los anteriores

#### Scenario: Entradas intactas
- **WHEN** termina una ejecución, con éxito o con error
- **THEN** el SHA-256 de `audio.wav`, `diarization.json` y `asr.json` es igual al de antes

### Requirement: Registro separado del error
Si una ejecución falla, el sistema SHALL escribir `transcription.error.json` con fecha, paso en que falló, tipo, mensaje y si existe un resultado válido anterior. Una ejecución exitosa posterior SHALL eliminarlo.

#### Scenario: Error registrado
- **WHEN** la ejecución falla porque `diarization.json` no cumple su contrato
- **THEN** `transcription.error.json` registra el paso de validación, el archivo y la regla incumplida

#### Scenario: Éxito posterior
- **WHEN** una ejecución termina bien después de una que falló
- **THEN** `transcription.error.json` ya no existe

### Requirement: Informe del éxito o el fracaso
Por línea de comandos, el sistema SHALL terminar con código 0 si tuvo éxito y 1 si falló, con el mensaje en la salida de errores. Como función, SHALL devolver el resultado o lanzar una excepción propia. Quien lo invoque SHALL poder decidir sin mirar los archivos de la carpeta.

#### Scenario: Fallo con resultado anterior presente
- **WHEN** una ejecución falla y queda un `transcription.json` válido de una ejecución anterior
- **THEN** el comando termina con código 1 y la función lanza la excepción

### Requirement: Rutas de entrada y salida
Por defecto, el sistema SHALL leer `audio.wav`, `diarization.json` y `asr.json` de la carpeta de la reunión y SHALL escribir sus resultados en ella. SHALL aceptar rutas explícitas para cada entrada y una carpeta de salida, que reemplazan a las de por defecto.

#### Scenario: Carpeta de la reunión
- **WHEN** se ejecuta con solo la carpeta de una reunión que contiene los tres archivos
- **THEN** los lee de ahí y escribe `transcription.json` y `transcription.meta.json` en esa carpeta

#### Scenario: Rutas explícitas
- **WHEN** se ejecuta con `figshare_v2_S26_objects_01.json` como diarización, un `asr.json` de otra carpeta y una carpeta de salida
- **THEN** usa esos archivos sin copiarlos ni renombrarlos y escribe solo en la carpeta de salida
