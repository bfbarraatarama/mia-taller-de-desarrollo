# Evaluación de recuperación en minutas

Tres flujos independientes: preparar datos, comparar minutas con fragmentación
normal y forzada, y evaluar el juez contra planillas humanas. El alcance y las
limitaciones están en el [plan](../../docs/minutas/plan-evaluacion-fidelidad-semantica.md).

## Requisitos

- El entorno del repositorio, los archivos AMI de `hito-2/muestra/ami/` y
  `hito-2/.cache/ami/ami_public_manual_1.6.2.zip`.
- MarianMT `Helsinki-NLP/opus-mt-en-es` en la caché de Hugging Face, revisión
  `5bc4493d463cf000c1f0b50f8d56886a392ed4ab`, para `preparar`. La preparación
  solo usa caché; no descarga modelos automáticamente.
- Ollama local con `qwen2.5:7b` para `inferir` y el juez para `juzgar` y
  `evaluar_juez`. No se admiten destinos externos.
- Los tres pares `{reunion}.csv` y `{reunion}.minuta.md` en
  `evaluacion/modular/resultados/planillas/`, o en la ruta `--planillas`.

Para descargar a la caché únicamente los archivos usados por el traductor:

```bash
.venv/bin/python -c 'from huggingface_hub import snapshot_download; from evaluacion.modular.traduccion import MODELO, REVISION, ARCHIVOS_MODELO; snapshot_download(MODELO, revision=REVISION, allow_patterns=ARCHIVOS_MODELO)'
```

Para instalar el juez, descargá el archivo
[`M-Prometheus-3B.i1-Q4_K_M.gguf`](https://huggingface.co/mradermacher/M-Prometheus-3B-i1-GGUF/blob/3d55806f3c809b6caccea702fd7e250fd5d16748/M-Prometheus-3B.i1-Q4_K_M.gguf)
de la revisión `3d55806f3c809b6caccea702fd7e250fd5d16748` a la carpeta
`evaluacion/fidelidad_minutas/`. Es un archivo grande (~2 GB), no lo agregues a
Git. Luego ejecutá:

```bash
ollama create m-prometheus-3b-i1:q4_k_m -f evaluacion/fidelidad_minutas/Modelfile
```

El SHA-256 esperado del archivo GGUF es
`03a2d4c481720b834d074428ab71567c751bc6998fee49cb5002d42d5e8913d0`.
La aplicación comprueba ese archivo y registra su hash, la revisión, el hash
del Modelfile y el digest de Ollama; verificá que la importación use ese
archivo. El digest de Ollama no prueba por sí solo el origen del modelo.
M-Prometheus es multilingüe
y está basado en Qwen 2.5 3B; es distinto del generador Qwen 2.5 7B. La
evaluación no garantiza su precisión en esta tarea.

## Ejecución

Desde la raíz, con un identificador nuevo para cada corrida:

```bash
.venv/bin/python -m evaluacion.fidelidad_minutas preparar --ejecucion prueba-01
.venv/bin/python -m evaluacion.fidelidad_minutas inferir --ejecucion prueba-01
.venv/bin/python -m evaluacion.fidelidad_minutas juzgar --ejecucion prueba-01
.venv/bin/python -m evaluacion.fidelidad_minutas reportar --ejecucion prueba-01

.venv/bin/python -m evaluacion.fidelidad_minutas.evaluar_juez --ejecucion juez-01
```

La evaluación del juez no depende de la preparación ni de las minutas nuevas.
Se puede usar `--salida RUTA` para cambiar la ubicación de resultados. La
carpeta predeterminada es `evaluacion/fidelidad_minutas/resultados/`, excluida
de Git. Los archivos humanos no se modifican. No se sobrescriben resultados:
si falla una etapa, corregí la causa y usá un identificador nuevo.

La preparación usa CPU y semillas fijas. Los dos modelos usan temperatura y
semilla cero; esto no garantiza salidas idénticas entre ejecuciones o equipos.
Una reunión cuyo bloque no pueda dividirse en dos partes entre 40 % y 60 %
falla explícitamente, en lugar de producir una comparación inválida. El juez
usa dos ejemplos por ítem en su evaluación independiente y tres para las
minutas nuevas; un empate es `incierto`. Sus citas no se comprueban.

## Pruebas

```bash
.venv/bin/python -m pytest -q -rs tests/evaluacion/test_fidelidad_*.py tests/minutas
```

Las pruebas usan proveedores simulados; no demuestran calidad semántica ni
sustituyen una ejecución con modelos reales.
