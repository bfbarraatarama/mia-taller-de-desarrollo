# Spec Delta

## Purpose

Identificar quién habla y cuándo en un audio normalizado de reunión, entregando segmentos por hablante con el contrato que consume la etapa de asociación, informando sin ambigüedad el éxito o el fracaso de cada ejecución y registrando los metadatos que permiten verificarla.

## ADDED Requirements

### Requirement: Validación del audio de entrada
El sistema SHALL verificar, antes de cargar el modelo, que el audio exista y sea un WAV de 16 000 Hz, 1 canal y PCM de 16 bits. Si no cumple, SHALL fallar indicando qué condición no se cumplió, sin modificar el audio ni un resultado válido anterior.

#### Scenario: Audio válido
- **WHEN** se diariza un WAV de 16 kHz, mono y PCM16 generado por la Etapa 1
- **THEN** el procesamiento continúa con la carga del modelo

#### Scenario: Archivo inexistente
- **WHEN** se indica una ruta de audio que no existe
- **THEN** la ejecución falla con un mensaje que nombra la ruta y no se crea ninguna carpeta ni archivo de resultados

#### Scenario: Formato no normalizado
- **WHEN** se indica un WAV estéreo, de 48 kHz o de 24 bits
- **THEN** la ejecución falla con un mensaje que indica el valor esperado y el encontrado, y el audio queda intacto

### Requirement: Compatibilidad con la salida de la Etapa 1
El sistema SHALL procesar sin conversión previa los WAV que graba la interfaz de la Etapa 1, incluido el de una grabación interrumpida. SHALL NOT modificar el WAV ni el reporte `.json` que la Etapa 1 escribe junto a él, y su carpeta de resultados SHALL ser distinta de ambos.

#### Scenario: Grabación hecha con la interfaz
- **WHEN** se diariza un WAV grabado con la interfaz de la Etapa 1 cuyo reporte tiene `estado: "completa"`
- **THEN** el WAV pasa la validación de entrada, se escribe un `diarization.json` dentro del contrato con al menos una etiqueta `SPEAKER_NN`, y la ejecución termina con éxito

#### Scenario: Archivos de la Etapa 1 intactos
- **WHEN** termina la diarización de una grabación de la Etapa 1
- **THEN** el SHA-256 del WAV y el de su reporte `.json` son iguales a los de antes, y los resultados están en `<carpeta>/<nombre>/`, separados del reporte `<carpeta>/<nombre>.json`

#### Scenario: Grabación interrumpida
- **WHEN** se diariza el WAV de una grabación cerrada a la fuerza, cuyo reporte quedó en estado "grabando"
- **THEN** se procesa como cualquier WAV válido, usando la duración de su cabecera, y la salida cumple el contrato

#### Scenario: Grabación interrumpida decodificable completa
- **WHEN** se verifica el WAV de una grabación interrumpida antes de diarizarlo
- **THEN** se decodifica completo sin errores, tanto leyendo todos sus cuadros como con FFmpeg, y la cantidad de muestras decodificadas coincide con la que declara la cabecera

### Requirement: Decodificador de audio disponible
El sistema SHALL leer el audio con FFmpeg. Si FFmpeg no está disponible o no puede decodificar el audio, SHALL fallar con un mensaje que lo nombra e indica cómo instalarlo y verificarlo.

#### Scenario: FFmpeg ausente
- **WHEN** se diariza un audio válido en una máquina donde FFmpeg no está disponible para la biblioteca de diarización
- **THEN** la ejecución falla con un mensaje que menciona FFmpeg y remite a las instrucciones de instalación y verificación

### Requirement: Contrato de diarization.json
El sistema SHALL escribir `diarization.json` con un único campo, `segments`: una lista de objetos con exactamente `start` y `end` (números, en segundos desde el inicio) y `speaker` (texto no vacío). Cada segmento SHALL cumplir `0 <= start < end <= duración del audio`, y los segmentos SHALL estar ordenados por `start`.

#### Scenario: Salida dentro del contrato
- **WHEN** termina una ejecución exitosa
- **THEN** `diarization.json` contiene solo `segments`, cada segmento tiene solo `start`, `end` y `speaker`, y todos cumplen `0 <= start < end <= duración`

#### Scenario: Segmentos ordenados
- **WHEN** se escribe `diarization.json`
- **THEN** los segmentos aparecen en orden de `start` creciente

### Requirement: Conservación del habla superpuesta
El sistema SHALL conservar los segmentos de hablantes distintos que se superponen en el tiempo. No SHALL recortarlos, fusionarlos ni eliminarlos para quitar el solapamiento.

#### Scenario: Dos personas hablan a la vez
- **WHEN** el modelo detecta a dos hablantes en un mismo intervalo
- **THEN** `diarization.json` contiene un segmento de cada hablante y sus intervalos se superponen

### Requirement: Etiquetas de hablante consistentes
El sistema SHALL usar una etiqueta por hablante detectado, con la forma `SPEAKER_NN`, y la misma etiqueta en todos los segmentos de ese hablante dentro de una ejecución.

#### Scenario: Dos hablantes
- **WHEN** se diariza un audio en que el modelo detecta dos voces
- **THEN** todos los segmentos usan exactamente dos etiquetas distintas con la forma `SPEAKER_NN`

### Requirement: Normalización de segmentos
El sistema SHALL recortar a los límites del WAV cada segmento que tenga una parte dentro del audio: un `end` posterior a la duración real pasa a esa duración y un `start` negativo pasa a 0, sea cual sea el exceso. Solo SHALL descartar los segmentos sin ninguna parte dentro del audio o vacíos tras redondear a 3 decimales. Ningún tiempo SHALL superar la duración real ni quedar negativo, y el resultado SHALL validarse otra vez contra el contrato.

#### Scenario: Regresión: el último tramo de habla de una grabación interrumpida
- **WHEN** el audio dura 32,5 s (520 000 cuadros a 16 kHz) y el modelo devuelve un segmento de 26,5922 a 32,5997 s
- **THEN** el segmento se escribe como `start` 26,592 y `end` 32,5, y los metadatos cuentan 1 segmento corregido y 0 descartados

#### Scenario: Exceso pequeño en el final
- **WHEN** el modelo devuelve un segmento con `end` 0,02 s mayor que la duración del audio
- **THEN** el segmento se escribe con `end` igual al mayor valor de 3 decimales que no supera la duración real, y los metadatos cuentan un segmento corregido

#### Scenario: Exceso grande con inicio dentro del audio
- **WHEN** el modelo devuelve un segmento que empieza dentro del audio y termina 0,5 s después de su duración
- **THEN** el segmento se escribe recortado a la duración real y los metadatos cuentan un segmento corregido

#### Scenario: Segmento completamente fuera del audio
- **WHEN** el modelo devuelve un segmento que empieza en la duración real del audio o después de ella
- **THEN** el segmento no se escribe y los metadatos cuentan un segmento descartado

#### Scenario: Inicio negativo
- **WHEN** el modelo devuelve un segmento de -0,3 a 1,0 s
- **THEN** el segmento se escribe con `start` igual a `0.0` y `end` igual a 1,0, y los metadatos cuentan un segmento corregido

#### Scenario: Redondeo hacia arriba en el final del audio
- **WHEN** el audio dura 12,3456875 s y un segmento termina exactamente en esa duración
- **THEN** el segmento se escribe con `end` igual a 12,345, que no supera la duración real, y el validador no informa violaciones

#### Scenario: Inicio que se redondea más allá del final
- **WHEN** el audio dura 12,3456875 s y un segmento va de 12,3455 a 12,3456 s
- **THEN** el segmento no se escribe, porque tras el redondeo y el recorte queda con `start >= end`, y los metadatos cuentan un segmento descartado

#### Scenario: Cero negativo
- **WHEN** un segmento empieza en -0,0004 s
- **THEN** se escribe con `start` igual a `0.0`, nunca `-0.0`

#### Scenario: Segmento degenerado tras el redondeo
- **WHEN** un segmento queda con `start` igual a `end` después de redondear a 3 decimales
- **THEN** el segmento no se escribe y los metadatos cuentan un segmento descartado

#### Scenario: Conteos en los metadatos
- **WHEN** en una ejecución se recortan 2 segmentos y se descarta 1
- **THEN** `diarization.meta.json` registra `segmentos_corregidos` igual a 2 y `segmentos_descartados` igual a 1, y `diarization.json` mantiene exactamente la estructura del contrato

### Requirement: Metadatos de la ejecución exitosa
Cuando una ejecución termina bien, el sistema SHALL escribir `diarization.meta.json` con: identificador de la ejecución, ruta, duración y SHA-256 del audio, modo pedido y dispositivo usado, modelo, versiones, `num_speakers` pedido, cantidad de hablantes y de segmentos, segmentos corregidos y descartados, tiempo de ejecución y fecha.

#### Scenario: Metadatos coherentes con el resultado
- **WHEN** termina una ejecución exitosa
- **THEN** `diarization.meta.json` registra el dispositivo efectivamente usado y una cantidad de hablantes y de segmentos igual a la de `diarization.json`

### Requirement: Correspondencia entre resultado y metadatos
El sistema SHALL registrar en `diarization.meta.json` el SHA-256 del `diarization.json` que escribió en la misma ejecución, de modo que pueda comprobarse que ambos archivos corresponden a la misma ejecución exitosa.

#### Scenario: Par consistente
- **WHEN** se calcula el SHA-256 de `diarization.json` después de una ejecución exitosa
- **THEN** coincide con el valor registrado en `diarization.meta.json`

#### Scenario: Par inconsistente detectado
- **WHEN** `diarization.json` y `diarization.meta.json` provienen de ejecuciones distintas
- **THEN** el validador informa que el par no corresponde a la misma ejecución

### Requirement: Conservación del último resultado válido ante un fallo
Si una ejecución falla, el sistema SHALL NOT sobrescribir ni eliminar un `diarization.json` o un `diarization.meta.json` previos de esa reunión, y SHALL NOT dejar archivos parciales con esos nombres. El audio SHALL quedar intacto.

#### Scenario: Falla con un resultado anterior
- **WHEN** existe un resultado válido de una ejecución anterior y una nueva ejecución falla durante la diarización
- **THEN** `diarization.json` y `diarization.meta.json` quedan byte a byte iguales a los anteriores

#### Scenario: Falla sin resultado anterior
- **WHEN** falla la primera ejecución de una reunión
- **THEN** no existe `diarization.json` ni `diarization.meta.json` en su carpeta de resultados

### Requirement: Publicación consistente del par
El sistema SHALL publicar `diarization.json` y `diarization.meta.json` de modo que un fallo durante la publicación deje el par anterior byte a byte o ningún par. Antes de reemplazar, SHALL respaldar el par vigente. Si falla un reemplazo, SHALL restaurar lo publicado, o borrarlo si no había par anterior, e informar la etapa `escritura`. Si la restauración falla, SHALL conservar los respaldos.

#### Scenario: Falla la publicación del meta con un resultado anterior
- **WHEN** existe un par válido y, en una nueva ejecución, `diarization.json` se publica pero falla la publicación de `diarization.meta.json`
- **THEN** el par queda byte a byte igual al anterior, pasa `validar_par`, no quedan `.tmp` ni `.bak`, y `diarization.error.json` registra la etapa `escritura` con `resultado_anterior_conservado: true`

#### Scenario: Falla la publicación del meta sin resultado anterior
- **WHEN** en la primera ejecución de una reunión falla la publicación de `diarization.meta.json`
- **THEN** no existe `diarization.json` ni `diarization.meta.json`, y no quedan `.tmp` ni `.bak`

#### Scenario: Falla la restauración
- **WHEN** falla la publicación del meta y también la restauración de `diarization.json` desde su respaldo
- **THEN** se informa el fallo original con una nota sobre la restauración, los `.bak` del par anterior se conservan con su contenido completo y el par inconsistente no se considera vigente

### Requirement: Par vigente verificado
El sistema SHALL considerar vigente un par solo si el `diarization_sha256` de su meta coincide con el SHA-256 de su `diarization.json`. Un par inconsistente SHALL NOT informarse como resultado anterior conservado.

#### Scenario: Par inconsistente en la carpeta
- **WHEN** la carpeta tiene un `diarization.json` cuyo SHA-256 no coincide con el `diarization_sha256` del meta, por ejemplo tras una interrupción abrupta entre los dos reemplazos
- **THEN** no se considera un resultado vigente: un error posterior registra `resultado_anterior_conservado: false` y `validar_par` informa la inconsistencia

### Requirement: Registro separado del error
Si una ejecución falla después de validar que el audio existe, el sistema SHALL escribir `diarization.error.json` en la carpeta de resultados con: identificador de la ejecución, fecha, etapa en que falló, tipo y mensaje del error, dispositivo pedido y si existe un resultado válido anterior. Una ejecución exitosa posterior SHALL eliminar ese archivo.

#### Scenario: Error registrado
- **WHEN** la GPU se queda sin memoria durante la diarización
- **THEN** `diarization.error.json` registra la etapa, el tipo de error, un mensaje que sugiere usar CPU y si se conservó un resultado anterior

#### Scenario: Éxito posterior
- **WHEN** una ejecución termina bien después de una que falló
- **THEN** `diarization.error.json` ya no existe en la carpeta de resultados

### Requirement: Informe del éxito o el fracaso
El sistema SHALL informar el resultado de cada ejecución sin depender de los archivos de la carpeta. Por línea de comandos, con código de salida 0 si tuvo éxito y distinto de 0 si falló, más un mensaje en la salida de errores. Como función, devolviendo el resultado o lanzando una excepción.

#### Scenario: Fallo con resultado anterior presente
- **WHEN** una ejecución falla y en la carpeta queda un `diarization.json` válido de una ejecución anterior
- **THEN** el comando termina con código distinto de 0 y la función lanza una excepción, de modo que quien la invoca no puede tomarla por exitosa

### Requirement: Separación de resultados por reunión
El sistema SHALL escribir los resultados de cada audio en una carpeta propia. Por defecto, una carpeta con el nombre del audio sin extensión, junto al audio. También SHALL admitir una carpeta de salida explícita.

#### Scenario: Dos grabaciones en la misma carpeta
- **WHEN** se diarizan dos grabaciones de la Etapa 1 guardadas en la misma carpeta, sin indicar carpeta de salida
- **THEN** cada una tiene sus propios `diarization.json` y `diarization.meta.json`, en carpetas distintas

### Requirement: Cantidad de hablantes opcional
Por defecto, el sistema SHALL dejar que el modelo estime la cantidad de hablantes. También SHALL aceptar `num_speakers`, opcional y entero mayor o igual que 1, para fijar la cantidad exacta. Ese valor SHALL registrarse en los metadatos y SHALL NOT modificar el contrato de salida.

#### Scenario: Sin indicar cantidad
- **WHEN** se diariza sin `num_speakers`
- **THEN** la cantidad de hablantes la estima el modelo y los metadatos registran `num_speakers` como nulo

#### Scenario: Cantidad exacta indicada
- **WHEN** se diariza con `num_speakers` igual a 2
- **THEN** `diarization.json` usa a lo sumo 2 etiquetas distintas y tiene la misma estructura que sin el parámetro

#### Scenario: Valor inválido
- **WHEN** se indica `num_speakers` igual a 0
- **THEN** la ejecución falla antes de cargar el modelo

### Requirement: Selección del dispositivo
El sistema SHALL aceptar los modos `auto` (por defecto), `cpu` y `cuda`. En `auto` SHALL usar CUDA si está disponible y CPU si no. En `cpu` SHALL usar CPU aunque haya GPU. En `cuda` sin CUDA disponible SHALL fallar, sin pasar a CPU.

#### Scenario: Automático sin GPU
- **WHEN** se diariza en modo `auto` en una máquina sin CUDA
- **THEN** la diarización corre en CPU y los metadatos registran `cpu`

#### Scenario: Automático con GPU
- **WHEN** se diariza en modo `auto` en una máquina con CUDA
- **THEN** la diarización corre en GPU y los metadatos registran `cuda`

#### Scenario: CPU forzada con GPU disponible
- **WHEN** se diariza en modo `cpu` en una máquina con CUDA
- **THEN** la diarización corre en CPU y los metadatos registran `cpu`

#### Scenario: CUDA pedida sin GPU
- **WHEN** se diariza en modo `cuda` en una máquina sin CUDA
- **THEN** la ejecución falla con un mensaje que dice que no hay CUDA disponible, y no se escribe `diarization.json`

### Requirement: Liberación de la GPU
Cuando la diarización corre en GPU, el sistema SHALL soltar sus referencias al modelo y a sus resultados en GPU y vaciar la caché de PyTorch al terminar, tanto si termina bien como si falla. La memoria asignada por PyTorch SHALL volver aproximadamente al nivel previo a la ejecución.

#### Scenario: Memoria liberada tras una ejecución
- **WHEN** termina una diarización en GPU llamada como función dentro de un proceso de Python
- **THEN** la memoria asignada por PyTorch en ese proceso no supera en más de 64 MiB a la medida antes de la llamada

#### Scenario: Memoria liberada tras un fallo
- **WHEN** una diarización en GPU falla durante la ejecución del modelo
- **THEN** la memoria asignada por PyTorch vuelve al mismo margen respecto de la medida antes de la llamada

### Requirement: Compatibilidad funcional entre CPU y GPU
El mismo código SHALL correr en CPU y en GPU sin cambios, y las salidas de ambos dispositivos SHALL cumplir el mismo contrato. La comprobación es funcional y de contrato: SHALL NOT exigirse que los segmentos, la cantidad de hablantes o el DER coincidan, ni presentarse como una equivalencia de precisión.

#### Scenario: Misma grabación en ambos dispositivos
- **WHEN** se diariza la misma grabación del dataset de test en modo `cpu` y en modo `cuda`
- **THEN** las dos ejecuciones terminan con éxito y sus salidas cumplen el contrato de `diarization.json`

#### Scenario: Diferencias entre dispositivos
- **WHEN** las salidas en CPU y en GPU de una grabación difieren en segmentos o en cantidad de hablantes
- **THEN** la prueba no falla por eso, y el reporte registra esas diferencias como información, sin calificarlas

### Requirement: Token de Hugging Face personal
El sistema SHALL obtener el token de la variable de entorno `HF_TOKEN` o, si no está definida, de un archivo `.env` local que no se versiona. El token SHALL NOT aparecer en la salida, en los mensajes, en `diarization.meta.json` ni en `diarization.error.json`.

#### Scenario: Token en .env
- **WHEN** `HF_TOKEN` no está en el entorno y sí en el archivo `.env`
- **THEN** el modelo se carga con ese token

#### Scenario: Token ausente
- **WHEN** el modelo no está en la caché local y no hay token ni en el entorno ni en `.env`
- **THEN** la ejecución falla con un mensaje que explica cómo configurar un token propio y aceptar las condiciones del modelo, sin mostrar ningún valor de token

### Requirement: Uso como comando y como función
El sistema SHALL poder ejecutarse desde la línea de comandos y llamarse como función de Python con los mismos parámetros: audio, carpeta de salida, modo de dispositivo y `num_speakers`. Al terminar bien por línea de comandos, SHALL mostrar la cantidad de hablantes y el tiempo de habla de cada uno, para revisarlos a mano.

#### Scenario: Línea de comandos exitosa
- **WHEN** se ejecuta el comando con un audio válido
- **THEN** escribe los resultados en la carpeta de la reunión, muestra cada etiqueta con su tiempo de habla y termina con código 0

### Requirement: Validador del contrato
El sistema SHALL incluir un validador que, dado un `diarization.json` y la duración del audio, informe todas las violaciones del contrato con el índice del segmento, o que no hay ninguna. Si además recibe el `diarization.meta.json`, SHALL comprobar que corresponden a la misma ejecución.

#### Scenario: Archivo válido
- **WHEN** se valida un `diarization.json` que cumple el contrato y tiene segmentos superpuestos
- **THEN** el validador informa cero violaciones

#### Scenario: Archivo inválido
- **WHEN** se valida un `diarization.json` con un segmento cuyo `end` supera la duración, otro sin `speaker` y un campo extra en la raíz
- **THEN** el validador informa las tres violaciones, cada una con su ubicación
