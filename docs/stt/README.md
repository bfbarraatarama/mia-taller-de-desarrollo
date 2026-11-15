# Transcripción automática (STT)

Desarrollo inicial del módulo: Felipe.

Convierte `audio.wav` en `asr.json`, con texto en castellano y marcas temporales por segmento y palabra. El módulo no asigna hablantes; esa responsabilidad corresponde a [asociación](../asociacion/README.md), de acuerdo con la [especificación del Hito 3](../../hito-3/pipeline-etapas-y-herramientas.md).

## Diseño

Se invoca Whisper una sola vez sobre el audio completo, con `language="es"` y `word_timestamps=True`. Frente a transcribir cada turno diarizado por separado, se conserva el contexto lingüístico del audio y se evita que los cortes de diarización determinen las entradas de STT. Los fragmentos muy cortos pueden perder contexto y favorecer texto espurio; no se dispone de una comparación cuantitativa específica de ambas estrategias en la PoC. El modelo `medium` es el baseline acordado; `small` y CPU son opciones de contingencia que deben registrarse, no resultados equivalentes. La justificación de la elección original está en la [definición de la PoC](../../hito-3/definicion-de-la-poc.md#311-el-modelo).

## Entorno y uso

Utilizar el [entorno general](../../README.md#entorno-único-para-todo-el-repositorio), incluido FFmpeg. Desde la raíz:

```python
from src.stt import process_asr

meta = process_asr(
    audio_path="audio.wav",
    output_path="asr.json",
    model_size="medium",
)
print(meta["segments_count"])
```

```bash
.venv/bin/python -m src.stt audio.wav -o asr.json -v
```

El nombre canónico `asr.json` se define en [`src/rutas.py`](../../src/rutas.py). Si no se selecciona dispositivo, se elige CUDA cuando está disponible o CPU. Para la contingencia de memoria pueden indicarse `model_size="small"` o `device="cpu"` (`--model small`, `--device cpu` en la CLI). La elección debe registrarse. El valor de aproximadamente 5 GB de VRAM para `medium` es la estimación de diseño original, no una medición del equipo objetivo.

`process_asr` no mantiene un modelo en caché: libera su referencia y llama a `free_gpu_memory()` también ante errores. Al utilizar directamente `load_whisper_model`, la liberación de la referencia y el llamado a `free_gpu_memory()` corresponden al invocante. En el flujo integrado, STT se ejecuta en un proceso temporal separado; la liberación de recursos no depende únicamente del recolector de Python.

## Contrato

Ejemplo de `asr.json`:

```json
{
  "language": "es",
  "segments": [
    {
      "start": 0.5,
      "end": 1.2,
      "text": "Vamos a revisar.",
      "words": [
        {"word": "Vamos", "start": 0.5, "end": 0.8},
        {"word": "a", "start": 0.8, "end": 0.9},
        {"word": "revisar.", "start": 0.9, "end": 1.2}
      ]
    }
  ]
}
```

La conversión descarta segmentos sin texto y palabras vacías o con tiempos originales inválidos; un segmento no vacío con intervalo original inválido produce un error. La validación exige intervalos finitos, no negativos y positivos, con fines que no superen la duración del audio más la tolerancia de 1 s cuando se informa esa duración. Los intervalos positivos que colapsan por redondeo se representan mediante una envolvente al milisegundo (véase [temporalidad](../temporalidad-transcripcion.md)). La fuente del contrato es [`src/stt/contrato.py`](../../src/stt/contrato.py), independiente de Whisper.

El texto del segmento se conserva aunque algunas palabras se descarten. No se garantiza que la concatenación de las palabras temporizadas reproduzca todo ese texto; la pérdida potencial durante la asociación todavía requiere tratamiento específico. No se deben inventar marcas temporales para ocultarla.

## Ejemplo y pruebas

Desde la raíz, `.venv/bin/python -m evaluacion.stt.ejemplos_peru` genera las salidas de PER-1 y PER-2 bajo `evaluacion/stt/generado/`, cuando están disponibles los originales. El [notebook de análisis](../../notebooks/stt_asr_peru.ipynb) consume esos resultados. El notebook de validación anterior se conserva en [notebooks históricos](../../notebooks/historicos/README.md), con sus contratos originales, sin presentarlo como evaluación vigente.

```bash
.venv/bin/python -m pytest -q -rs tests/stt
```

La prueba del contrato no sustituye la medición de WER ni la evaluación integral en castellano rioplatense.
