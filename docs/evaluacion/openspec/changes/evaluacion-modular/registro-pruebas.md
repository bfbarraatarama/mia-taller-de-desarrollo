# Registro de pruebas

Evaluación modular de la PoC (issue #13). Lo medido, separado de lo estimado. Las cifras de métricas no tienen umbral (§2.3).

## Entorno de referencia

| | |
|---|---|
| Máquina | Fedora 43, kernel 7.2.11; NVIDIA RTX 3050 Laptop 6 GB, driver 580.178.04; 31 GB de RAM |
| Python | 3.12.16, entorno único del repositorio (perfil `requirements-cu128.txt`, con `torchcodec` 0.7.0 de PyPI: ver issue #18) |
| Paquetes | torch 2.8.0+cu128, pyannote.audio 4.0.7, pyannote.metrics 4.2.0, openai-whisper 20250625, transformers 5.22.1, pydantic 2.14.1 |
| Herramientas | FFmpeg 7.1.5, 7-Zip 26.04 (`7zz`, con `SIETE_ZIP`), Ollama 0.30.10 con `qwen2.5:7b` |
| Código | `main` en `0e52daa` (integración, PR #12) más esta rama; sin el PR #19 |

## Nivel 1 · pruebas automáticas

| Suite | Resultado |
|---|---|
| `tests/evaluacion/` | 73 pruebas, un archivo por requisito, cada escenario de las specs con su nombre |
| Suite completa (`pytest -q tests hito-2/tests`, con `SIETE_ZIP`) | 893 aprobadas, 2 omitidas (un caso solo sin GPU; faltan los RTTM locales de S26), 6 deseleccionadas, 52 subtests |

Sin `SIETE_ZIP`, en Fedora fallan las 2 pruebas que leen los RAR reales (`test_inventarios_reales` y `test_miembro_de_figshare_real`): el 7-Zip del sistema no lee RAR. Los tests de la tarea 6.5 pasaron desde el primer intento, porque el requisito ya lo cumplía el diseño de las tareas anteriores.

## Nivel 2 · corridas con los datos reales

### Preparación (tareas 2.2 a 4.2)

| Corrida | Resultado |
|---|---|
| Originales | 8 de 8 verificados contra `hito-2/fuentes.lock.json`; Common Voice bajado desde la web, mismo SHA-256 que el fijado |
| `preparar`, 1.ª corrida (16/11/2026) | 82 elementos en 427 s, pico de 2,5 GB de RAM; `contenido_sha256` `68b317117c84676f835d58473e8a9c82aa94cefb87d26f6cde487a919416b456` |
| `preparar`, 2.ª corrida | 396 s; `contenido` idéntico y el mismo `contenido_sha256` (escenario «Misma semilla, misma muestra») |
| `preparar --verificar` | Código 0, muestra intacta (escenario «Muestra intacta») |

Muestra: OpenSLR `arf_03398_01736798627`, `arm_03397_00908571298`, `arf_01208_01340718114`; Common Voice `common_voice_es_19635568.mp3`, `common_voice_es_38141239.mp3`; Figshare S22 (20 tareas), S23 (24) y S25 (30), 78,8 min; AMI IB4005 (533 turnos, 25 ítems, sin roles), IS1009c (291 turnos, 19 ítems), TS3009a (502 turnos, 12 ítems). Se descartaron 166 turnos de AMI que vienen sin texto en la tabla del Hito 2.

### Inferencia (tarea 5.3)

| | |
|---|---|
| Corrida | 16/11/2026, GPU sin otros procesos; 82 elementos en 7471 s (2 h 4 min), sin fallas |
| Por fuente | AMI 37,5 min (13 a 16 min por reunión); clips 0,9 min; Figshare 86,1 min (mediana 68 s, máximo 172 s por tarea) |
| VRAM | Pico de 4870 MiB de 6144 (durante las minutas) |
| Reutilización | Una 2.ª `inferir` reutilizó los 82 elementos en 0,4 s sin cargar modelos (escenario «Reutilización») |

### Evaluación (tareas 5.1 y 6.1 a 7.1)

`evaluar` tarda unos 7 s y no carga modelos. Con la GPU oculta, reproduce byte a byte los reportes versionados (escenario «Recalcular métricas»).

| Criterio o métrica | Resultado |
|---|---|
| Funcionamiento modular (§2.3) | **Cumple, 4/4**: diarización 74/74, STT 79/79, asociación 74/74, minutas 77/77 |
| WER y CER (STT) | OpenSLR 9,1 % y 4,2 % (22 palabras); Common Voice 0 % y 0 % (9); Figshare 27,0 % y 20,1 % (13 125): 727 sustituciones, 78 inserciones y 2735 borrados. Excluidos de la referencia de Figshare: 62 etiquetas, 283 fragmentos y 53 tokens sin letras |
| DER estricto, DER NIST y JER (diarización) | S22 18,9 %, 7,9 % y 36,6 %; S23 28,4 %, 15,8 % y 48,7 %; S25 20,2 %, 10,4 % y 37,7 %; total 21,3 %, 10,7 % y 41,0 %. Confusión: 436 de 820 s de error. Cantidad de hablantes correcta en 65 de 74 tareas |
| Palabras bien atribuidas (asociación) | 87,3 % de 9492 (S22 91,5 %, S23 82,7 %, S25 86,9 %); sin superposición 86,1 %. 801 palabras fuera del habla de referencia y 1 sin hablante. Marcas: 318 de 318 `overlap` y 184 de 262 `ambiguous` caen sobre superposición real |
| Ítems recuperados (minutas) | Planillas generadas: 56 ítems sin marcar (tarea 7.2) |
| Exposición previa | Pendiente de confirmar: uso de S22 y S23 en el desarrollo de la Etapa 2 |

## Comprobación con el PR #19

Con los validadores de la rama del PR #19 (`19bbd6a`), las 77 salidas de `transcription.json` de esta corrida (74 de Figshare y 3 de AMI) siguen dentro del contrato y la Etapa 5 las lee.

## Pendiente

- Tarea 7.2: marcado de la planilla de minutas por Felipe o Luisa.
- Confirmar con la responsable de la Etapa 2 que S22 y S23 no se usaron para desarrollar.
