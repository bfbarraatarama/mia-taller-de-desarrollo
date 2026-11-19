"""
Run Stage 3 (STT) on the Humyn LATAM Peruvian (PER-1, PER-2) and Venezuelan (VEN-1, VEN-2)
recordings, plus CORDEBA_K randomly selected CORdeBA recordings (COR-<number>).

Writes evaluacion/stt/generado/<ID>/asr.json. The audio is reused if already present;
otherwise it is extracted from the raw Humyn parquet in hito-2/.cache/humyn.

    python -m evaluacion.stt.ejemplos            # medium model
    python -m evaluacion.stt.ejemplos --dry-run  # only check the audio
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from pathlib import Path

from src.rutas import ARCHIVO_ASR, DIRECTORIO_PROYECTO

from src.stt.asr_core import DEFAULT_MODEL_SIZE, process_asr

logger = logging.getLogger(__name__)

HUMYN_CACHE = DIRECTORIO_PROYECTO / "hito-2" / ".cache" / "humyn"
CORDEBA_CACHE = DIRECTORIO_PROYECTO / "hito-2" / ".cache" / "cordeba"
OUTPUT_BASE = DIRECTORIO_PROYECTO / "evaluacion" / "stt" / "generado"

HUMYN_RECORDINGS = {
    "PER-1": "Spanish_Peru_1.wav",
    "PER-2": "Spanish_Peru_2.wav",
    "VEN-1": "Spanish_Venezuela_1.wav",
    "VEN-2": "Spanish_Venezuela_2.wav",
}

CORDEBA_K = 3
CORDEBA_SEED = 20261010
# Recordings (hito-2 audit) excluded from the random draw, with the reason:
CORDEBA_EXCLUDED = {
    16: "audio cannot be decoded (CordeBA_0016.wma)",
    9: "transcript has 1-2 turns: speakers not separated",
    19: "transcript has 1-2 turns: speakers not separated",
    24: "transcript has 1-2 turns: speakers not separated",
    2: "under 100 words/min: transcript likely incomplete",
    12: "under 100 words/min: transcript likely incomplete",
    21: "under 100 words/min: transcript likely incomplete",
}


def select_cordeba(k: int = CORDEBA_K, seed: int = CORDEBA_SEED) -> dict[str, str]:
    """Pick k CORdeBA recordings at random (fixed seed) from the curated list."""
    curated = [n for n in range(1, 25) if n not in CORDEBA_EXCLUDED]
    chosen = sorted(random.Random(seed).sample(curated, k))
    return {f"COR-{n:04d}": f"CordeBA_{n:04d}.mp3" for n in chosen}


RECORDINGS = {**HUMYN_RECORDINGS, **select_cordeba()}


def ensure_audio(test_id: str, archivo: str) -> Path:
    """Return the audio path for a recording (CORdeBA: original; Humyn: extracted WAV)."""
    if test_id not in HUMYN_RECORDINGS:
        audio_path = CORDEBA_CACHE / archivo
        if not audio_path.exists():
            raise FileNotFoundError(f"No audio for {archivo}: expected {audio_path}")
        return audio_path

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
    parser = argparse.ArgumentParser(description="Run STT on the Humyn recordings")
    parser.add_argument("--model", default=DEFAULT_MODEL_SIZE, help="Whisper model size")
    parser.add_argument("--device", choices=["cuda", "cpu"], help="Default: auto-detect")
    parser.add_argument("--dry-run", action="store_true", help="Only check the audio; skip Whisper")
    parser.add_argument("--ids", nargs="+", choices=list(RECORDINGS), help="Default: all")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    failed = 0
    for test_id, archivo in RECORDINGS.items():
        if args.ids and test_id not in args.ids:
            continue
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
