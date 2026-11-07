# STT (Stage 3: ASR)

Converts audio and a diarization into a speaker-attributed transcription.

- **Input:** a normalized WAV file and a `diarization.json`.
- **Output:** a `transcription.json` with the text of each diarized segment.

Diarization defines the timestamp grid. Whisper provides the words. Whisper timestamps only decide which segment each word belongs to.

## Setup

From the repository root:

```bash
pip install -r src/STT/requirements_asr.txt
```

## Contracts

**diarization.json**

```json
{
  "segments": [
    {"start": 0.0, "end": 4.2, "speaker": "Speaker A"},
    {"start": 4.2, "end": 9.8, "speaker": "Speaker B"}
  ]
}
```

- `segments` must be a non-empty list.
- Each segment needs `start`, `end` (seconds), and `speaker`.
- `start` must be less than `end`.

**transcription.json**

```json
{
  "segments": [
    {"start": 0.0, "end": 4.2, "speaker": "Speaker A", "text": "hola a todos"}
  ]
}
```

Only diarization segments that receive at least one word are emitted. `process_asr` also returns a metadata dict (`model`, `device`, `duration`, `segments_count`).

## Matching algorithm

1. Transcribe the WAV with Whisper (`language="es"`), producing words with `start`/`end`.
2. Drop words with empty text or `start >= end`.
3. For each word, find the diarization segment where `segment.start <= word.start < segment.end`.
4. Join each segment's words with spaces to produce its `text`.

Words whose start falls outside every segment are not assigned.

## Usage

```python
from src.STT import process_asr

meta = process_asr(
    audio_path="data/ASR/tmp/example/audio.wav",
    diarization_path="data/ASR/tmp/example/diarization.json",
    output_path="data/ASR/tmp/example/transcription.json",
    model_size="base",
    words_path="data/ASR/tmp/example/whisper_words.json",  # optional: raw Whisper words
)
print(meta["segments_count"])
```

To build a diarization from Humyn LATAM turns:

```python
from src.STT import humyn_turns_to_diarization

diarization = humyn_turns_to_diarization(turns_df, recording_id="PER-1")
```

`turns_df` needs the columns `archivo`, `hablante`, `inicio`, and `fin`. Turns with zero duration are skipped.

## Test runner

`test_humyn_latam.py` runs the pipeline on two Humyn LATAM Peruvian recordings (`PER-1`, `PER-2`). It expects the preprocessed Humyn data under `hito-2/`.

```bash
python -m src.STT.test_humyn_latam --dry-run   # validate contracts, no Whisper
python -m src.STT.test_humyn_latam -v          # full run
```

Outputs go to `data/ASR/tmp/test_asr/<ID>/`.
