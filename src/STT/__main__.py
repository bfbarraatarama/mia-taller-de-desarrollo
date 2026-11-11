"""CLI: PYTHONPATH=src python -m STT audio.wav -o asr.json"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rutas import ARCHIVO_ASR

from .asr_core import DEFAULT_MODEL_SIZE, process_asr


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3 STT: audio.wav -> asr.json")
    parser.add_argument("audio", type=Path, help="Normalized WAV file")
    parser.add_argument("-o", "--output", type=Path, default=Path(ARCHIVO_ASR))
    parser.add_argument("--model", default=DEFAULT_MODEL_SIZE, help="Whisper model size")
    parser.add_argument("--device", choices=["cuda", "cpu"], help="Default: auto-detect")
    parser.add_argument("--dry-run", action="store_true", help="Only check the audio; skip Whisper")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    try:
        meta = process_asr(
            audio_path=args.audio,
            output_path=args.output,
            model_size=args.model,
            verbose=args.verbose,
            dry_run=args.dry_run,
            device=args.device,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
