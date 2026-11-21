# Spec Delta

## Purpose

Define los requisitos de comportamiento de la captura de audio en vivo desde micrófono y audio del sistema, y de la reproducción del audio capturado, garantizando que el resultado es usable como entrada del pipeline.

## ADDED Requirements

### Requirement: Captura de audio desde micrófono
El sistema SHALL capturar audio desde el micrófono seleccionado y producir un archivo WAV a 16 kHz, mono, PCM 16 que sea una entrada válida para el pipeline.

#### Scenario: Captura básica desde micrófono en Windows
- **GIVEN** un micrófono disponible y seleccionado en la interfaz
- **WHEN** se inicia y detiene una grabación de al menos 10 segundos
- **THEN** el archivo WAV resultante tiene frecuencia de 16 kHz, 1 canal, formato PCM 16, y la duración registrada en `ingesta.json` coincide con el tiempo de grabación

#### Scenario: Captura con audio del sistema en Windows
- **GIVEN** un dispositivo de audio del sistema disponible (ej. CABLE Output o loopback)
- **WHEN** se selecciona junto al micrófono y se graba mientras hay audio reproduciéndose
- **THEN** el archivo WAV contiene la mezcla de ambas fuentes y sigue siendo válido para el pipeline

#### Scenario: Captura básica desde micrófono en Linux
- **GIVEN** un micrófono disponible en Linux
- **WHEN** se inicia y detiene una grabación de al menos 10 segundos
- **THEN** el archivo WAV resultante tiene frecuencia de 16 kHz, 1 canal, formato PCM 16

### Requirement: Escritura continua a disco durante la captura
Durante la grabación, el sistema SHALL escribir el audio al archivo WAV de forma continua, de modo que si el proceso se interrumpe abruptamente el archivo quede válido hasta los últimos fragmentos grabados.

#### Scenario: Corte de energía durante grabación
- **GIVEN** una grabación en curso
- **WHEN** el proceso se termina abruptamente (sin Stop explícito)
- **THEN** el archivo WAV resultante es un WAV válido con el audio grabado hasta el momento del corte, legible con soundfile o ffmpeg

### Requirement: Selección de dispositivos de entrada
El sistema SHALL listar los dispositivos de audio disponibles y permitir al usuario seleccionar el micrófono y el dispositivo de audio del sistema de forma independiente.

#### Scenario: Listado de dispositivos disponibles
- **GIVEN** la interfaz abierta en un sistema con al menos un micrófono
- **WHEN** el usuario accede a la selección de dispositivos
- **THEN** la lista muestra al menos un dispositivo de entrada y el nombre del dispositivo es legible

#### Scenario: Dispositivo no disponible
- **GIVEN** un dispositivo previamente seleccionado que ya no está disponible (desconectado)
- **WHEN** se intenta iniciar la captura
- **THEN** el sistema muestra un mensaje de error claro sin bloquear la interfaz

### Requirement: Reproducción del audio capturado
El sistema SHALL permitir reproducir el archivo de audio capturado desde la interfaz antes de enviarlo al pipeline.

#### Scenario: Reproducción exitosa
- **GIVEN** un archivo de grabación completado
- **WHEN** el usuario activa la reproducción desde la interfaz
- **THEN** el audio se escucha a través del dispositivo de salida por defecto y el control de reproducción muestra el progreso

#### Scenario: Interrupción de la reproducción
- **GIVEN** una reproducción en curso
- **WHEN** el usuario detiene la reproducción manualmente
- **THEN** la reproducción se detiene y la interfaz vuelve al estado disponible
