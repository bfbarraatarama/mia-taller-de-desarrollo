# Evaluación de la Etapa 3 (STT)

Mide el WER de Whisper sobre siete grabaciones con referencia de texto. Resultados y conclusiones: [`EVALUACION.md`](EVALUACION.md). Las salidas de Whisper (`generado/`) las ignora git; lo versionado es [`manifiesto.json`](manifiesto.json) y [`resultados/`](resultados): `wer.json` y una copia de cada `asr.json` en `resultados/asr/<ID>.json`.

| Archivo | Qué hace |
|---|---|
| `ejemplos.py` | Define las grabaciones y transcribe cada una a `generado/<ID>/asr.json`. Opciones: `--ids`, `--model`, `--device`, `--dry-run`, `-v` |
| `wer.py` | Calcula el WER por grabación y el promedio. Escribe `resultados/wer.json` (versionado). Opción: `--ids`, que sobrescribe el archivo solo con esas grabaciones |
| `manifiesto.py` | Escribe o verifica (`--verificar`) `manifiesto.json` |
| `resultados/wer.json` | WER por grabación y promedio de la última corrida |
| `resultados/asr/<ID>.json` | Hipótesis de Whisper usada para cada WER (copiada por `wer.py`), para reproducir el cálculo sin volver a transcribir |
| `manifiesto.json` | Selección, parámetros del sorteo, exclusiones y SHA-256 del audio y de cada referencia normalizada |

Desde la raíz del repo:

```
python -m evaluacion.stt.ejemplos                       # todas (CPU: ~10-15 min por grabación)
python -m evaluacion.stt.ejemplos --ids COR-0010 COR-0014 COR-0015
python -m evaluacion.stt.wer
python -m evaluacion.stt.manifiesto --verificar
pytest tests/evaluacion/test_stt_wer.py
```

## Grabaciones

| IDs | Fuente | Referencia | Tiempos |
|---|---|---|---|
| `PER-1`, `PER-2`, `VEN-1`, `VEN-2` | Humyn LATAM (`hito-2/.cache/humyn`) | `transcript_json` | Sí |
| `COR-0010`, `COR-0014`, `COR-0015` | CORdeBA (`hito-2/.cache/cordeba`) | `metadata.csv` | No |

Las de CORdeBA salen de un sorteo de `k = 3` con semilla `20261010` sobre las grabaciones restantes tras las exclusiones. Los parámetros están en `ejemplos.py` y en el manifiesto.

### Exclusiones de CORdeBA

Basadas en la auditoría de `hito-2` ([EDA](../../hito-2/2-eda-de-viabilidad.md) y [datasheet](../../hito-2/3-datasheet.md)):

| Grabaciones | Motivo |
|---|---|
| `0016` | El audio (`.wma`) no se puede decodificar |
| `0009`, `0019`, `0024` | La transcripción tiene 1 o 2 turnos: no separa hablantes |
| `0002`, `0012`, `0021` | Menos de 100 palabras/min: la transcripción probablemente está incompleta |

## Cálculo del WER

1. **ASR:** se concatena el texto de todos los segmentos de `asr.json`.
2. **Recorte (solo Humyn):** se usan únicamente los segmentos que empiezan antes del último tiempo de la referencia, porque la referencia cubre menos audio que la grabación (aprox. 11 de 15 min). CORdeBA no tiene tiempos y se usa el ASR completo.
3. **Normalización** (ASR y referencia): minúsculas, sin acentos (se pierde la `ñ`), sin signos de puntuación ni símbolos (incluye `¿ ¡`, guiones, `[ ]` y `=`) y espacios colapsados. Las palabras dentro de `[ ]` (solapamiento en CORdeBA) se conservan.
4. **WER** con `jiwer`. El promedio es el de los WER por grabación, sin ponderar por palabras.

## Limitaciones conocidas

- **CORdeBA transcribe cómo suena** ("hacemo", "muuy", "estamo") e incluye muletillas ("eee", "ehh"). Whisper escribe la forma estándar y omite las muletillas, lo que infla el WER (36–47 % frente a 12–28 % en Humyn). La normalización actual no lo corrige.
- Los números se comparan tal como salen: Whisper escribe cifras y la referencia, palabras.
- Con tres grabaciones de CORdeBA y cuatro de Humyn, el promedio no es una estimación general.
- CORdeBA es CC BY-NC-SA 4.0 (solo uso no comercial) y los audios de Humyn y CORdeBA no se redistribuyen desde el repo.
