# Spec Delta

## Purpose

Medir los escenarios de §2.1 y la recuperación ante interrupciones de la definición de la PoC con entradas fijadas, corridas por la aplicación, comprobaciones automáticas y un protocolo para un tercero.

## ADDED Requirements

### Requirement: Entradas fijadas
Cada escenario SHALL tener una entrada armada de forma determinista desde datos públicos o congelados y registrada con su SHA-256 en un manifiesto versionado. Antes de correr, SHALL verificarse contra el manifiesto y fallar nombrando la diferencia.

#### Scenario: Ruido reproducible
- **WHEN** se arma dos veces la entrada de 2.1.4 con la misma semilla
- **THEN** los dos WAV tienen el mismo SHA-256

#### Scenario: Entrada alterada
- **WHEN** la entrada de un escenario no coincide con el manifiesto
- **THEN** la corrida falla antes de procesar y nombra el archivo

### Requirement: Comprobaciones automáticas
Para cada escenario corrido, SHALL comprobarse sobre los archivos de la aplicación lo verificable de su «Entonces»: 2.1.2 y 2.1.3, solapamientos conservados y marcas de ambigüedad; 2.1.3, cantidad de etiquetas; 2.1.4, audio conservado y estado de cada etapa; 2.1.5, minuta por fragmentos o aviso con la transcripción conservada. El resultado SHALL registrar sí, no o manual por comprobación.

#### Scenario: Seis o más hablantes
- **WHEN** se comprueba la salida de 2.1.3
- **THEN** el reporte indica cuántas etiquetas detectó, cuántas intervenciones quedaron como ambiguas y si el audio se conservó

#### Scenario: Minuta por fragmentos
- **WHEN** se comprueba la salida de 2.1.5
- **THEN** el reporte indica cuántos bloques de extracción usó la minuta y que hay una sola transcripción para los 30 archivos

### Requirement: Prueba de recuperación
SHALL grabarse con la captura de la aplicación al menos 2 minutos, cerrarla a la fuerza y medir lo perdido como tiempo grabado hasta el corte menos la duración del WAV. SHALL comprobarse que el WAV se puede procesar y que figura entre las grabaciones interrumpidas. Cumple con 5 s perdidos o menos.

#### Scenario: Corte forzado
- **WHEN** la captura se cierra con `kill -9` a los 130 s
- **THEN** el reporte registra el tiempo grabado, la duración del WAV, lo perdido, si es procesable y si figura como interrumpida

### Requirement: Protocolo para un tercero
SHALL existir una lista para recorrer cada escenario con la aplicación abierta, con su entrada, los pasos y una columna sí o no por cada «Entonces», incluidas las comprobaciones que solo se ven en la interfaz.

#### Scenario: Comprobación solo visual
- **WHEN** un «Entonces» depende de la interfaz, como el mismo nombre en dos etiquetas
- **THEN** figura en el protocolo y el reporte automático lo marca como manual
