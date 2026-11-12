# Tasks

Orden de D9: esqueleto de punta a punta primero. En cada tarea, primero los tests de sus escenarios.

## 1. Preparación

- [x] 1.1 Estructura de `PoC/paso4_asociacion/` (paquete, `tests/`, `evaluacion/`) y `requirements-dev.txt` con `pytest`
- [x] 1.2 Ejemplo ideal (D10): guion, script con espeak-ng que genera `audio.wav`, `diarization.json`, `asr.json` y `referencia.json` · escenario: Ejemplo ideal

## 2. Esqueleto de punta a punta

- [x] 2.1 Validación del audio · escenarios: Audio normalizado, Audio no normalizado
- [x] 2.2 Validación de `diarization.json` · escenarios: Diarización de la Etapa 2, Segmento después del audio
- [x] 2.3 Validación de `asr.json` con margen de 1,0 s y recortes · escenarios: Fin dentro del margen de la Etapa 3, Palabra que queda vacía tras el recorte, Fin fuera del margen de la Etapa 3, Segmento sin palabras
- [x] 2.4 Asignación por máxima superposición (D1) y armado de intervenciones (D4) · escenario: Happy path con dos hablantes
- [x] 2.5 Estructura, valores y validación de la propia salida · escenarios: Campos exactos, Salida dentro del contrato, Redondeo y texto, Salida inválida detectada
- [x] 2.6 Escritura con `.tmp` + `os.replace`, `transcription.meta.json` y `transcription.error.json` · escenarios: Metadatos coherentes con el resultado, Falla con un resultado anterior, Entradas intactas, Error registrado, Éxito posterior
- [x] 2.7 CLI con códigos 0/1, rutas por defecto y explícitas, sin etiquetado · escenarios: Fallo con resultado anterior presente, Carpeta de la reunión, Rutas explícitas, Sin interfaz
- [x] 2.8 Lectura por la Etapa 5 (`leer_transcripcion` de `src/minutas/entrada.py`, en su entorno) · escenario: Lectura por la Etapa 5
- [x] 2.10 Publicación con respaldo y reversión, y resultado anterior verificado por SHA-256 (observación de Bruno en #8, mismo criterio que la Etapa 2) · escenarios: Falla la publicación del meta con un resultado anterior, Falla la publicación sin resultado anterior, Falla la restauración, Resultado inconsistente en la carpeta
- [ ] 2.9 Avisar a Bruno y a Luisa: hay `transcription.json` para integrar y para la tarea 7.5

## 3. Atribución completa

- [x] 3.1 Empates por continuidad (D2) y palabras en huecos con margen de 0,25 s (D3)
- [x] 3.2 Marcas `overlap` y `ambiguous` en milisegundos enteros (D5) · escenarios: Dos personas hablan a la vez, Interrupción breve, Roce de bordes, Segundo hablante en el 30 %, Texto sin respaldo en la diarización, Valores límite, Sin hablante
- [x] 3.3 Entradas sin habla · escenarios: Sin habla transcrita, Diarización vacía con texto
- [x] 3.4 Cualquier cantidad de hablantes · escenario: Seis o más hablantes

## 4. Fragmentos (D6)

- [x] 4.1 Tramos solos, candidatos de al menos la media, semilla y permutación · escenarios: Candidatos de al menos la media, Misma entrada mismo fragmento, Otro fragmento sin repetir
- [x] 4.2 Recorte central y respaldos · escenarios: Tramo de más de 15 s, Sin tramo de 5 s, Nunca habla solo
- [x] 4.3 Texto del fragmento por punto medio de las palabras

## 5. Modelo de fichas, sin Qt (D8)

- [x] 5.1 Orden por tiempo de habla · escenario: Orden por tiempo de habla
- [x] 5.2 Normalización y unificación de nombres, aviso de tildes · escenarios: Misma persona en dos etiquetas, Nombres que difieren solo en tildes, Nombre vacío
- [x] 5.3 Autocompletado y contador · escenarios: Autocompletado, Contador de fragmentos
- [x] 5.4 Opciones de cierre y `speakers.json` con el fragmento en pantalla · escenarios: Volver a las fichas, Seguir sin nombres, Cancelar, Fragmento en pantalla al confirmar

## 6. Diálogo y reproducción (PySide6, sounddevice)

- [ ] 6.1 `QDialog` modal con `QScrollArea` y una ficha por etiqueta · escenarios (lista manual): Ocho fichas, Grabar durante el etiquetado
- [ ] 6.2 Reproducción de un solo fragmento a la vez, ▶/■ · escenarios (lista manual): Una reproducción a la vez, Detener
- [ ] 6.3 Pregunta al cerrar sin confirmar

## 7. Panel de procesamiento (D7)

- [ ] 7.1 Acordar con Bruno `--hasta transcribir` y `--desde minuta`
- [ ] 7.2 Dos corridas con las fichas en el medio y latencia sumada · escenarios: Happy path con interfaz, Latencia sin el etiquetado
- [ ] 7.3 Volver a etiquetar sin repetir la GPU · escenario: Volver a etiquetar sin repetir la GPU
- [x] 7.4 Nombres del contrato en los botones: `minutes.md` y `transcription.json`

## 8. Integración con datos reales (nivel 2)

- [x] 8.1 Correr las Etapas 2 (#8) y 3 (#9) en la GPU sobre las 4 grabaciones propias; resultados de GPU para las tareas 7.3 y 7.4 de la Etapa 2
- [x] 8.2 Etapa 4 sobre esas salidas: contrato al 100 % y lectura por la Etapa 5
- [x] 8.3 Medir proporción de intervenciones con `overlap`, con `ambiguous` y de palabras decididas por D2 y D3, sin cambiar umbrales
- [ ] 8.4 Validación 7.5 con Luisa

## 9. Muestra congelada (nivel 3)

- [ ] 9.1 Contrato al 100 % sobre las salidas de las Etapas 2 y 3 en las 3 sesiones de Figshare de 2.3 · depende de la muestra congelada (semana 7)

## 10. Cierre

- [ ] 10.1 Lista de chequeo manual: audio, diálogo modal, 8 fichas, aviso de superposición
- [x] 10.2 `README.md` del módulo: instalación, uso, contratos y resultados
