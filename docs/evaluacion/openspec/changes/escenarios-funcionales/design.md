# Design

## Contexto

§2.3 mide los escenarios con «un input real o preparado por escenario, fijado antes de la semana 9» y «un tercero recorre los escenarios con la aplicación abierta y marca sí o no»; la recuperación, con «una grabación propia de al menos 2 minutos, cortada cerrando el proceso a la fuerza». La captura escribe el WAV mientras graba y deja el `.json` con estado «grabando» si se corta; `src/captura/recuperacion.py` lista las grabaciones interrumpidas.

## Decisiones

### D1. Alcance para el checkpoint

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **Lo que no requiere grabar personas: 2.1.2 a 2.1.5 y la recuperación; happy path y 2.1.1 pendientes** | **Elegida** |
| B | Todo, con grabaciones propias (incluida una reunión con terminología) | Descartada: requiere personas que consientan y guion; no llega al 17/11 |
| C | Solo el plan | Descartada: el checkpoint mostraría 0 escenarios medidos |

### D2. Entrada de 2.1.3 (seis o más hablantes)

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **ICSI Bro015 completa: 17 min, 6 hablantes** | **Elegida** |
| B | ICSI Bmr025: 33 min, 8 hablantes | Descartada: el doble de tiempo y más difícil de recorrer |
| C | Un extracto local de 30 s | Descartada: rara vez hablan 6 personas en 30 s |

Motivo: es la reunión de ICSI más corta que cumple §2.1.3. Está en inglés: el escenario mide diarización y marcas, no la transcripción.

### D3. Entrada de 2.1.5 (transcripción más larga que el contexto)

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **Sesión S25 de Figshare de la muestra congelada, como 30 archivos en orden** | **Elegida** |
| B | Una reunión larga de ICSI | Descartada: en inglés; la minuta saldría de una transcripción mala |
| C | Una reunión de AMI traducida | Descartada: es texto, no pasa por la aplicación |

Motivo: castellano, ya verificada con hash, supera el bloque del LLM y además ejercita la carga de varios archivos del happy path.

### D4. Entrada de 2.1.4 (ruido)

| Alternativa | Descripción | Resultado |
|---|---|---|
| **A** | **Ruido sintético con semilla sobre una tarea de la muestra** | **Elegida** |
| B | Grabación propia con ruido real | Descartada: no repetible y requiere grabar |
| C | Las dos | Descartada: suma una grabación |

Motivo: reproducible y comparable con la misma tarea limpia.

## Precisiones

| Tema | Precisión |
|---|---|
| Entrada de 2.1.2 | La tarea de la muestra con más habla superpuesta en la referencia (métrica de diarización del #21): `figshare-S25-12`, 16,2 s superpuestos en 4,2 min. Dos personas, no se sabe si de voces similares |
| Entrada de 2.1.4 | `figshare-S22-01` con ruido rosa a 5 dB de SNR respecto de la señal, semilla 20261010 |
| Corrida | `src.pipeline ejecutar` con la misma configuración que la evaluación modular (Whisper `medium`, pyannote en CUDA, `qwen2.5-7b`, 5 secciones), sin fichas de hablantes (la línea de comandos las saltea) |
| Recuperación | `src.captura.captura` sin `--duracion`, cerrada con `kill -9` a los 130 s de empezar a grabar; lo perdido es el tiempo grabado hasta el corte menos la duración del WAV que queda |
| Reparto | Las comprobaciones automáticas cubren lo que se verifica en archivos; lo que se ve en la interfaz (fichas, mismo nombre en dos etiquetas, lista de interrumpidas al reiniciar) va en el protocolo del tercero |
| Medición de lo perdido | El inicio es la aparición del `.json` «grabando» que la captura escribe al abrir el WAV (sondeo cada 50 ms); el corte, el envío de SIGKILL. Resolución de unos ±0,1 s, despreciable contra el límite de 5 s. Lo procesable se comprueba corriendo el pipeline sobre el WAV recuperado; la lista de interrumpidas, con `consultar_grabaciones_interrumpidas` |
| Interfaz | La aplicación busca grabaciones interrumpidas en la carpeta de su campo «salida» al iniciar: el protocolo indica elegir la carpeta de la prueba y reabrir |
| Carpeta por corrida (revisión del #24) | `correr` usa una carpeta nueva para cada escenario; la de una corrida anterior se conserva como `<escenario>.anterior`. `comprobar` recibe el código de salida de la corrida evaluada: con código distinto de 0, «Termina o informa la falla» solo es «sí» si la aplicación informó el error y no quedó como completada |
| Superposición (revisión del #24) | Los segundos superpuestos cuentan solo dos o más etiquetas distintas a la vez; los turnos de una misma etiqueta se unen antes. Sobre las corridas del 16/11 el resultado no cambia (15,187 s en 2.1.2) |
