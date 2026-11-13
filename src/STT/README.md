# STT (Stage 3)

Converts audio into text with timestamps per segment and per word. Responsible: Felipe.

- **Input:** a normalized WAV file (`audio.wav`).
- **Output:** `asr.json`.

This stage does **not** use the diarization and does not assign speakers. Associating `asr.json` with `diarization.json` to produce `transcription.json` is Stage 4. See `hito-3/pipeline-etapas-y-herramientas.md`.

The whole audio is transcribed once with Whisper (`language="es"`); it is not split by diarization segment.

## Setup

From the repository root (PyTorch as in Stage 2, FFmpeg on the system):

```bash
pip install -r src/STT/requirements_asr.txt
```

## Contract

**asr.json**

```json
{
  "language": "es",
  "segments": [
    {
      "start": 0.5,
      "end": 4.2,
      "text": "Vamos a revisar los resultados.",
      "words": [
        {"word": "Vamos", "start": 0.5, "end": 0.8},
        {"word": "a", "start": 0.8, "end": 0.9}
      ]
    }
  ]
}
```

- Segments with empty text are dropped; words with empty text or `start >= end` are dropped.
- Every segment and word has `start < end`, and ends do not exceed the audio duration (1 s tolerance).

## Usage

```python
from STT import process_asr

meta = process_asr(
    audio_path="audio.wav",
    output_path="asr.json",
    model_size="medium",  # default
)
print(meta["segments_count"])
```

Like the other modules, it runs with `PYTHONPATH=src`; the default output name (`asr.json`) is `ARCHIVO_ASR` in [`src/rutas.py`](../rutas.py). From the command line:

```bash
PYTHONPATH=src python -m STT audio.wav -o asr.json -v
```

**Memory fallback (risk 1.4.1):** use `model_size="small"` (~2 GB) or `device="cpu"` (`--model small`, `--device cpu`), and record the change. The `medium` model needs ~5 GB of VRAM. The model is not cached: `process_asr` holds the only reference and releases it (also on errors) before returning, then calls `free_gpu_memory()`, so the GPU is free for the next sequential stage. If you use `load_whisper_model` directly, `del` the model and call `free_gpu_memory()` yourself.

## Tests

```bash
PYTHONPATH=src pytest src/STT/test_asr_core.py
```
