# Spec Delta

## Purpose

Que el usuario escuche un fragmento de cada hablante detectado, lea su texto y escriba su nombre, para que la transcripción y la minuta usen nombres reales (2.2, punto 5).

## ADDED Requirements

### Requirement: Contrato de speakers.json
Al confirmar el etiquetado, el sistema SHALL escribir `speakers.json` con una entrada por cada etiqueta de `diarization.json`: `{"<etiqueta>": {"name", "clip_start", "clip_end"}}`. `name` SHALL ser texto no vacío o `null`; `clip_start` y `clip_end` SHALL ser números con 3 decimales y `0 <= clip_start < clip_end <= duración`, y SHALL corresponder al fragmento que estaba en pantalla al confirmar. Por línea de comandos, sin interfaz, `speakers.json` SHALL NOT escribirse.

#### Scenario: Fragmento en pantalla al confirmar
- **WHEN** el usuario pide «Otro fragmento» dos veces en la ficha de `SPEAKER_00`, no reproduce ninguno y confirma
- **THEN** `clip_start` y `clip_end` de `SPEAKER_00` son los del tercer fragmento

#### Scenario: Nombre vacío
- **WHEN** el usuario deja vacío el nombre de `SPEAKER_01` o escribe solo espacios
- **THEN** `SPEAKER_01` tiene `name: null` en `speakers.json` y en sus intervenciones de `transcription.json`

#### Scenario: Sin interfaz
- **WHEN** se procesa por línea de comandos sin etiquetado
- **THEN** no existe `speakers.json` y todas las intervenciones de `transcription.json` tienen `name: null`

### Requirement: Normalización y unificación de nombres
El sistema SHALL normalizar cada nombre quitando los espacios de los extremos y reduciendo los internos a uno. Dos nombres SHALL considerarse la misma persona si coinciden sin distinguir mayúsculas; en ese caso todas sus etiquetas SHALL llevar la primera forma escrita, en el orden de las fichas. Nombres que difieren solo en tildes SHALL NOT unificarse; la interfaz SHALL avisarlo antes de confirmar, sin cambiarlos.

#### Scenario: Misma persona en dos etiquetas
- **WHEN** el usuario escribe `Luisa` en `SPEAKER_00` y `luisa ` en `SPEAKER_02`
- **THEN** ambas etiquetas tienen `name: "Luisa"` en `speakers.json` y en `transcription.json`, y conservan sus etiquetas originales en `speaker`

#### Scenario: Nombres que difieren solo en tildes
- **WHEN** el usuario escribe `Martín` en `SPEAKER_00` y `Martin` en `SPEAKER_01` y presiona Confirmar
- **THEN** la interfaz avisa que los nombres difieren solo en tildes, y si el usuario confirma igual, quedan como dos personas distintas

### Requirement: Fichas por hablante (2.2, punto 5)
Al terminar la asociación, el sistema SHALL mostrar una ficha por etiqueta de `diarization.json`, ordenadas de mayor a menor tiempo de habla, cada una con la etiqueta, el tiempo de habla, un botón para reproducir el fragmento, «Otro fragmento», el texto del fragmento y un campo para el nombre. Las fichas SHALL poder recorrerse sea cual sea su cantidad.

#### Scenario: Orden por tiempo de habla
- **WHEN** `SPEAKER_01` habla 6 min y `SPEAKER_00` habla 3 min
- **THEN** la ficha de `SPEAKER_01` aparece primero

#### Scenario: Ocho fichas
- **WHEN** hay 8 etiquetas
- **THEN** se pueden ver y completar las 8 fichas, con desplazamiento si no entran en la ventana

### Requirement: Cierre de las fichas sin confirmar
Si el usuario cierra la ventana de fichas sin confirmar, el sistema SHALL preguntar con tres opciones: «Volver a las fichas» (por defecto), «Seguir sin nombres» y «Cancelar». Los resultados de las Etapas 2 y 3 SHALL conservarse en todos los casos.

#### Scenario: Volver a las fichas
- **WHEN** el usuario cierra la ventana y presiona Enter en la pregunta
- **THEN** vuelven las fichas con los nombres que ya había escrito

#### Scenario: Seguir sin nombres
- **WHEN** el usuario elige «Seguir sin nombres»
- **THEN** se escribe `transcription.json` con `name: null`, no se escribe `speakers.json` y el procesamiento sigue con la Etapa 5

#### Scenario: Cancelar
- **WHEN** el usuario elige «Cancelar»
- **THEN** no se escriben `transcription.json` ni `speakers.json`, el procesamiento se detiene y `diarization.json` y `asr.json` quedan intactos

### Requirement: Candidatos al azar de al menos la media
Para cada etiqueta, el sistema SHALL elegir el fragmento al azar entre los tramos en que habla solo con duración ≥ máx(media de sus tramos solos, 5 s), con una semilla derivada de `diarization.json` (D6 de `design.md`).

#### Scenario: Candidatos de al menos la media
- **WHEN** `SPEAKER_00` tiene tramos solos de 2, 4, 6, 8 y 30 s (media 10 s)
- **THEN** el fragmento sale solo del tramo de 30 s, recortado a sus 15 s centrales

#### Scenario: Misma entrada, mismo fragmento
- **WHEN** se procesa dos veces el mismo `diarization.json`
- **THEN** cada etiqueta recibe el mismo primer fragmento y la misma secuencia de «Otro fragmento»

### Requirement: Recorte a 15 s
Un tramo elegido de más de 15 s SHALL recortarse a sus 15 s centrales.

#### Scenario: Tramo de más de 15 s
- **WHEN** el único candidato de `SPEAKER_00` es un tramo solo de 40,0 a 70,0 s
- **THEN** el fragmento es de 47,5 a 62,5 s

### Requirement: Respaldos del fragmento
Si una etiqueta no tiene candidatos, el sistema SHALL usar su tramo solo más largo. Si no habla nunca sola, SHALL usar su turno más largo y la ficha SHALL avisar que se superpone con otra voz.

#### Scenario: Sin tramo de 5 s
- **WHEN** los tramos solos de `SPEAKER_01` duran 1,2, 2,8 y 3,5 s
- **THEN** el fragmento es el tramo de 3,5 s

#### Scenario: Nunca habla solo
- **WHEN** todos los turnos de `SPEAKER_01` caen dentro de turnos de `SPEAKER_00`
- **THEN** el fragmento es su turno más largo y la ficha avisa que se superpone con otra voz

### Requirement: Otro fragmento
«Otro fragmento» SHALL mostrar el siguiente candidato de la permutación sin repetir hasta agotarlos; después SHALL seguir con los respaldos y volver a empezar.

#### Scenario: Otro fragmento sin repetir
- **WHEN** `SPEAKER_00` tiene 3 candidatos y el usuario pide «Otro fragmento» dos veces
- **THEN** ve los 3 candidatos, cada uno una sola vez
