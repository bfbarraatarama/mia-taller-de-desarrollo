# Evaluación modular de la PoC

Muestra congelada de la [definición de la PoC, §2.3](../../hito-3/definicion-de-la-poc.md#23-criterios-de-aceptación) y ejecutor que evalúa los cuatro módulos sobre ella: el criterio «Funcionamiento modular» (contratos) y las métricas sin umbral. Issue #13.

Decisiones, specs y tareas: [OpenSpec](../../docs/evaluacion/openspec/changes/evaluacion-modular/). Resultados medidos: [registro de pruebas](../../docs/evaluacion/openspec/changes/evaluacion-modular/registro-pruebas.md).

## La muestra

| Fuente | Elementos | Módulos | Referencia |
|---|---|---|---|
| OpenSLR 61 | 3 clips de 3 personas (2 mujeres, 1 hombre) | STT | Texto de cada clip |
| Common Voice 26 rioplatense (split `test`) | 2 clips (una mujer, un hombre) | STT | Texto de cada clip |
| UBA Games, Figshare v2 | Sesiones S22, S23 y S25 completas: 74 tareas, 78,8 min, mezcla mono de los dos canales | Cadena real 2→3→4→5 | Frases por canal (texto, tiempos y hablante) |
| AMI | IB4005, IS1009c y TS3009a, traducidas con MarianMT (sintéticas) | Minutas | Ítems de la minuta de referencia, traducidos |

Todo se elige con la semilla 20261010 y queda fijado por SHA-256 en [`muestra.manifest.json`](muestra.manifest.json) (`contenido_sha256` `68b31711…`). S26 se excluye por ser material de desarrollo, y S27 a S30 por tener la transcripción incompleta.

## Uso

Desde la raíz del repositorio, con el [entorno único](../../README.md#entorno-único-para-todo-el-repositorio):

```bash
.venv/bin/python -m evaluacion.modular preparar             # verifica los originales y congela la muestra (unos 7 min, CPU)
.venv/bin/python -m evaluacion.modular preparar --verificar  # comprueba la muestra contra el manifiesto, sin tocarla
.venv/bin/python -m evaluacion.modular inferir              # corre los módulos (unas 2 h en una RTX 3050 de 6 GB)
.venv/bin/python -m evaluacion.modular evaluar              # contratos y métricas desde lo guardado (segundos, sin GPU)
```

Códigos de salida: 0 terminó; 1 falló, con el motivo en la salida de errores. `inferir` reutiliza lo ya inferido con el mismo insumo y la misma configuración; `--rehacer` lo fuerza. `evaluar` termina con 1 si no se cumple el criterio «Funcionamiento modular».

### Originales

`preparar` no descarga nada: si falta un original o su hash no coincide, indica cómo obtenerlo.

| Original | Cómo obtenerlo |
|---|---|
| OpenSLR 61 y AMI | `.venv/bin/python -I hito-2/scripts/descargar_fuentes.py slr61` y `… anotaciones` |
| Figshare (`phrases.rar`, `wavs.rar`, 722 MB) | `.venv/bin/python -I hito-2/scripts/descargar_fuentes.py uba_games_figshare` |
| Common Voice 26 rioplatense (447 MB) | Cuenta en Mozilla Data Collective con los términos aceptados: `MDC_API_KEY=… .venv/bin/python -I hito-2/scripts/descargar_fuentes.py common_voice`. También se puede bajar desde la web: tiene otro nombre, pero el mismo SHA-256; se guarda en `hito-2/.cache/common_voice/` con el nombre del lock |

Los RAR se leen con 7-Zip. En Fedora, el 7-Zip del sistema no lee RAR: hace falta `SIETE_ZIP` apuntando a un 7-Zip con RAR (por ejemplo, el `7zz` oficial).

## Archivos

| Ruta | Contenido | ¿Se versiona? |
|---|---|---|
| `config.toml` | Semilla, carpetas, modelos (Whisper `medium`, `qwen2.5-7b`, 5 secciones) y originales; los hashes salen del lock del Hito 2 | Sí |
| `muestra.manifest.json` | Muestra congelada: `contenido` con su SHA-256, y `ejecucion` | Sí |
| `exposicion.toml` | Exposición previa declarada por fuente, con evidencia | Sí |
| `datos/` | Audio normalizado y traducciones de AMI (unos 290 MB) | No |
| `inferencia/` | Salidas de los módulos, cada una con `inferencia.json` | No |
| `resultados/` | `contratos.json`, `metricas_stt.json`, `metricas_diarizacion.json`, `metricas_asociacion.json`, `planilla_minutas.json`, `exposicion.json` y `planillas/` | Sí |

| Módulo | Qué hace |
|---|---|
| `originales.py` | Verifica tamaño y hash de cada original |
| `seleccion.py` | Selección determinista de clips, sesiones y reuniones |
| `audio.py` | Cada elemento como carpeta de reunión hecha con `ingestar` del pipeline; mezcla mono de Figshare |
| `traduccion.py` | Traducción de AMI con MarianMT y su `transcription.json` (rol como nombre) |
| `muestra.py` | Preparación, manifiesto y verificación |
| `inferencia.py` | Un proceso por elemento con el comando de su etapa |
| `contratos.py` | Validadores públicos de cada etapa |
| `metricas_stt.py`, `metricas_diar.py`, `metricas_asociacion.py` | WER y CER; DER y JER con `evaluacion/diarizacion/der.py`; palabras bien atribuidas |
| `planilla.py`, `exposicion.py` | Planilla de minutas para marcar; informe de exposición previa |

## Resultados (corrida del 16/11/2026)

| Criterio o métrica | Resultado |
|---|---|
| Funcionamiento modular (§2.3) | **Cumple**: diarización 74/74, STT 79/79, asociación 74/74, minutas 77/77 |
| WER (STT) | Figshare 27,0 % (CER 20,1 %; 77 % de los errores son borrados), OpenSLR 9,1 %, Common Voice 0 % |
| DER estricto, DER NIST y JER (diarización) | 21,3 %, 10,7 % y 41,0 % (S26, Etapa 2: 23,1 %, 12,3 % y 40,0 %) |
| Palabras bien atribuidas (asociación) | 86,1 % sin superposición; 87,3 % en total |
| Ítems recuperados (minutas) | Pendiente: 56 ítems a marcar en `resultados/planillas/` |

Las métricas no tienen umbral (§2.3). Detalle por sesión y por archivo en `resultados/`.

## Planilla de minutas

La marca una persona que no ejecutó la inferencia, siguiendo [`resultados/planillas/LEEME.md`](resultados/planillas/LEEME.md). Después, `evaluar` resume lo marcado sin modificar la planilla.

## Limitaciones

- La muestra es chica, como pide §2.3: Figshare son 3 sesiones de 2 personas en un juego, no reuniones, y AMI está traducida automáticamente.
- En la atribución de palabras, el grupo «con superposición» no es informativo con 2 hablantes: se acepta cualquiera de los dos canales.
- Exposición previa: no se puede descartar que Whisper, pyannote o Qwen hayan visto estos corpus públicos, y falta confirmar que S22 y S23 (alcance inicial de la Etapa 2) no se usaron localmente para desarrollar ([`resultados/exposicion.json`](resultados/exposicion.json)).
- Las salidas son de `main` antes del PR #19; con sus validadores siguen dentro del contrato.
