"""
Run Stage 3 (STT) on the two Humyn LATAM Peruvian recordings (PER-1, PER-2).

Writes data/ASR/tmp/test_asr/<ID>/asr.json. The audio is reused if already present;
otherwise it is extracted from the raw Humyn parquet in hito-2/.cache/humyn.

    PYTHONPATH=src python -m STT.ejemplos_peru            # medium model
    PYTHONPATH=src python -m STT.ejemplos_peru --dry-run  # only check the audio
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rutas import ARCHIVO_ASR, DIRECTORIO_PROYECTO

from .asr_core import DEFAULT_MODEL_SIZE, process_asr

logger = logging.getLogger(__name__)

HUMYN_CACHE = DIRECTORIO_PROYECTO / "hito-2" / ".cache" / "humyn"
OUTPUT_BASE = DIRECTORIO_PROYECTO / "data" / "ASR" / "tmp" / "test_asr"

PER_RECORDINGS = {
    "PER-1": "Spanish_Peru_1.wav",
    "PER-2": "Spanish_Peru_2.wav",
}


def ensure_audio(test_id: str, archivo: str) -> Path:
    """Return the WAV path for a recording, extracting it from Humyn if missing."""
    audio_path = OUTPUT_BASE / test_id / "audio.wav"
    if audio_path.exists():
        return audio_path

    import pyarrow.parquet as pq

    for parquet in sorted(HUMYN_CACHE.glob("*.parquet")):
        df = pq.read_table(parquet).to_pandas()
        match = df[df["file_name"] == archivo]
        if not match.empty:
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            audio_path.write_bytes(match.iloc[0]["audio"]["bytes"])
            return audio_path

    raise FileNotFoundError(
        f"No audio for {archivo}: expected {audio_path} or a Humyn parquet in {HUMYN_CACHE}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run STT on the Peruvian Humyn recordings")
    parser.add_argument("--model", default=DEFAULT_MODEL_SIZE, help="Whisper model size")
    parser.add_argument("--device", choices=["cuda", "cpu"], help="Default: auto-detect")
    parser.add_argument("--dry-run", action="store_true", help="Only check the audio; skip Whisper")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    failed = 0
    for test_id, archivo in PER_RECORDINGS.items():
        try:
            audio_path = ensure_audio(test_id, archivo)
            meta = process_asr(
                audio_path=audio_path,
                output_path=OUTPUT_BASE / test_id / ARCHIVO_ASR,
                model_size=args.model,
                verbose=args.verbose,
                dry_run=args.dry_run,
                device=args.device,
            )
            logger.info(
                f"OK {test_id}: {meta['status']}, {meta['segments_count']} segments, "
                f"{meta['duration']:.0f}s, device={meta['device']}"
            )
        except Exception as e:
            failed += 1
            logger.error(f"FAILED {test_id}: {e}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
