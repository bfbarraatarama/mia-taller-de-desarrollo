# Spec Delta

## Purpose

Correr los cuatro módulos de la PoC sobre la muestra congelada, por separado y en cadena, guardar sus salidas y medir desde lo guardado el cumplimiento de los contratos (criterio «Funcionamiento modular» de §2.3) y las métricas sin umbral de cada módulo.

## ADDED Requirements

### Requirement: Inferencia sobre la muestra verificada
`inferir` SHALL verificar el manifiesto antes de correr y SHALL ejecutar: STT en los 5 clips y en Figshare; diarización y la cadena 2→3→4→5 en Figshare; minutas en AMI. Cada salida SHALL guardarse con la versión de los modelos, la configuración, el dispositivo y el tiempo. Una salida ya guardada para la misma entrada y configuración SHALL reutilizarse salvo `--rehacer`.

#### Scenario: Muestra alterada
- **WHEN** se ejecuta `inferir` y un archivo de la muestra no coincide con el manifiesto
- **THEN** falla antes de cargar ningún modelo y nombra el archivo

#### Scenario: Reutilización
- **WHEN** se ejecuta `inferir` dos veces sin cambiar la muestra ni la configuración
- **THEN** la segunda corrida no carga modelos y deja las salidas intactas

### Requirement: Contratos de los cuatro módulos
`evaluar` SHALL validar cada salida con el validador de su etapa (`validar_diarizacion`, `validate_asr_contract`, `validar_transcripcion` y el modelo de `src/minutas/contratos.py`) y SHALL informar, por módulo, salidas válidas sobre totales y cada violación con archivo y regla. El criterio se cumple con 4/4 módulos al 100 %.

#### Scenario: Todas válidas
- **WHEN** todas las salidas de los cuatro módulos cumplen su contrato
- **THEN** el reporte indica 4/4 módulos al 100 % y `evaluar` termina con código 0

#### Scenario: Una salida fuera de contrato
- **WHEN** un `diarization.json` guardado tiene un segmento con `start >= end`
- **THEN** el reporte indica diarización por debajo del 100 %, nombra el archivo y la regla, y `evaluar` termina con código distinto de 0

### Requirement: Métricas de transcripción
`evaluar` SHALL calcular WER y CER por archivo y agregados, contra la referencia de cada clip y de cada tarea de Figshare, después de pasar a minúsculas y quitar la puntuación, conservando las tildes. SHALL registrar las sustituciones, inserciones y borrados, sin umbral.

#### Scenario: Normalización
- **WHEN** la referencia es «Está bien, sí.» y la hipótesis es «esta bien si»
- **THEN** se cuentan 2 sustituciones y 0 errores por mayúsculas o puntuación

### Requirement: Métricas de diarización
`evaluar` SHALL calcular DER estricto, DER con tolerancia NIST de ±0,25 s y JER por tarea y agregados en Figshare, con `evaluacion/diarizacion/der.py` y su política de etiquetas, sin umbral.

#### Scenario: Misma configuración que S26
- **WHEN** se evalúa una tarea de Figshare
- **THEN** el reporte usa la misma tolerancia en los bordes, el mismo tratamiento del solapamiento y la misma política de etiquetas que `EVALUACION_S26.md`

### Requirement: Atribución de palabras de la asociación
`evaluar` SHALL calcular, en la cadena de Figshare, el porcentaje de palabras de `transcription.json` cuyo hablante coincide con el canal de la frase de referencia que las contiene, separado en palabras con y sin superposición de referencia, y cuántas intervenciones `ambiguous` caen sobre superposición real.

#### Scenario: Palabra en superposición
- **WHEN** una palabra cae donde las frases de referencia de los dos canales se superponen
- **THEN** se cuenta en el grupo con superposición, no en el general

#### Scenario: Correspondencia de etiquetas
- **WHEN** la diarización llama `SPEAKER_00` al participante del canal 2
- **THEN** la atribución usa la correspondencia de etiquetas de la evaluación de diarización, no el nombre de la etiqueta

### Requirement: Planilla de minutas
`evaluar` SHALL generar, por reunión de AMI, una planilla con cada ítem de la minuta de referencia traducida y la minuta producida, con una columna sí/no para que una persona marque si fue recuperado. Si la planilla ya está marcada, SHALL resumir los ítems recuperados por tipo sin modificarla.

#### Scenario: Planilla sin marcar
- **WHEN** se evalúa una reunión de AMI por primera vez
- **THEN** se escribe la planilla con todos los ítems de referencia y la columna sí/no vacía

#### Scenario: Planilla marcada
- **WHEN** se evalúa de nuevo con la planilla ya marcada
- **THEN** el reporte cuenta los ítems recuperados por tipo y la planilla no cambia

### Requirement: Evaluación sin inferencia
`evaluar` SHALL calcular contratos y métricas solo desde las salidas guardadas, sin cargar modelos. Si falta una salida, SHALL informarla como faltante, no como violación.

#### Scenario: Recalcular métricas
- **WHEN** se ejecuta `evaluar` en una máquina sin GPU, con las salidas guardadas
- **THEN** obtiene los mismos contratos y métricas que en la máquina donde se infirió

### Requirement: Informe de exposición previa
`evaluar` SHALL incluir, por fuente, si sus datos se usaron para desarrollar alguna etapa o si pudieron entrar al entrenamiento de algún modelo usado, con la evidencia o la falta de ella.

#### Scenario: Fuente de desarrollo excluida
- **WHEN** se genera el informe
- **THEN** indica que S26 se usó para desarrollar la diarización y la asociación y que quedó fuera de la muestra
