# Spec Delta

## Purpose

Define los requisitos de comportamiento ante interrupciones del pipeline: cancelación explícita por el usuario, recuperación desde checkpoints tras fallos, y reanudación cuando los archivos de entrada no están disponibles temporalmente.

## ADDED Requirements

### Requirement: Cancelación del procesamiento en curso
El sistema SHALL permitir cancelar el pipeline en cualquier etapa y dejar el directorio de salida en un estado conocido que permita reintentar el procesamiento posteriormente.

#### Scenario: Cancelación durante diarización
- **GIVEN** un pipeline en la etapa `diarizar`
- **WHEN** el usuario acciona la cancelación desde la GUI o envía señal al proceso
- **THEN** el pipeline se detiene, `workflow.json` queda con estado `cancelado` y no quedan archivos parciales que corrompan una ejecución posterior

#### Scenario: Cancelación durante generación de minuta
- **GIVEN** un pipeline en la etapa `minuta`
- **WHEN** el usuario acciona la cancelación
- **THEN** el pipeline se detiene, las etapas previas completadas (hasta `asociar`) quedan con estado `completado` en `workflow.json` y pueden reutilizarse en un reintento

#### Scenario: Reintento tras cancelación
- **GIVEN** un directorio con estado `cancelado`
- **WHEN** se inicia el procesamiento con las mismas fuentes
- **THEN** el pipeline retoma desde la última etapa completada, sin reprocesar lo que ya estaba correcto

### Requirement: Recuperación desde checkpoint tras interrupción abrupta
Si el proceso termina de forma no controlada durante el pipeline, el sistema SHALL detectar el estado inconsistente en la siguiente ejecución y retomar desde el último checkpoint verificado.

#### Scenario: Proceso terminado durante transcripción
- **GIVEN** un proceso cortado mientras ejecutaba la etapa `transcribir`
- **WHEN** se relanza el procesamiento sobre el mismo directorio
- **THEN** el sistema revalida los artefactos existentes, descarta los de la etapa interrumpida y retoma desde la última etapa consistente

#### Scenario: Archivo de workflow corrupto
- **GIVEN** un `workflow.json` con contenido inválido o truncado
- **WHEN** se intenta procesar el directorio
- **THEN** el sistema reporta el error con un mensaje claro y no continúa con datos potencialmente incorrectos

### Requirement: Reanudación cuando el archivo de entrada no está disponible
Si el archivo de audio original no está en su ruta original al momento de reintentar el procesamiento, el sistema SHALL usar la copia conservada en el directorio de la reunión si es verificablemente idéntica al original.

#### Scenario: Archivo original movido o eliminado
- **GIVEN** un pipeline cancelado con el audio original ya ingestado (copia en el directorio de la reunión) y el archivo original movido a otra ubicación
- **WHEN** se reintenta el procesamiento indicando la ruta original
- **THEN** el sistema detecta la copia conservada, verifica su integridad (SHA-256) y la usa como fuente sin error

#### Scenario: Copia conservada con hash distinto
- **GIVEN** una copia del audio en el directorio de la reunión que no coincide con el hash esperado
- **WHEN** se reintenta el procesamiento
- **THEN** el sistema rechaza la copia y reporta que la fuente no está disponible con un mensaje que identifica el archivo

### Requirement: Exclusión de acceso concurrente
El sistema SHALL impedir que dos procesos intenten procesar el mismo directorio de reunión simultáneamente, reportando el conflicto con un error identificable.

#### Scenario: Dos instancias sobre el mismo directorio en Windows
- **GIVEN** un pipeline en curso sobre un directorio en Windows
- **WHEN** una segunda instancia intenta procesar el mismo directorio
- **THEN** la segunda instancia falla con un error de tipo `ReunionOcupada` y no corrompe el estado del primer proceso

#### Scenario: Dos instancias sobre el mismo directorio en Linux
- **GIVEN** un pipeline en curso sobre un directorio en Linux
- **WHEN** una segunda instancia intenta procesar el mismo directorio
- **THEN** la segunda instancia falla con un error de tipo `ReunionOcupada` y no corrompe el estado del primer proceso
