#!/usr/bin/env python3
"""
Test script: Validate ASR on Humyn LATAM Peruvian recordings (PER-1, PER-2).

Loads Humyn turns from parquet, extracts audio, converts to diarization.json,
runs ASR, and saves transcription.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from pathlib import Path

import pyarrow.parquet as pq
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.STT.asr_core import process_asr, validate_diarization_contract
from src.STT.humyn_adapter import humyn_turns_to_diarization

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HUMYN_CACHE = REPO_ROOT / "hito-2" / ".cache" / "humyn"
HUMYN_PARQUET_RAW = list(HUMYN_CACHE.glob("*.parquet"))
HUMYN_TURNOS = REPO_ROOT / "hito-2" / "muestra" / "humyn" / "turnos.parquet"
OUTPUT_BASE = REPO_ROOT / "data" / "ASR" / "tmp" / "test_asr"

# Peruvian recording identifiers
PER_RECORDINGS = {
    "PER-1": "Spanish_Peru_1.wav",
    "PER-2": "Spanish_Peru_2.wav"
}


def extract_audio_to_wav(audio_bytes: bytes, output_path: Path) -> None:
    """Write audio bytes to WAV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)


def test_recording(
    test_id: str,
    archivo_name: str,
    turns_df: pd.DataFrame,
    verbose: bool = False,
    dry_run: bool = False
) -> dict:
    """
    Test ASR on one Peruvian recording.
    
    Args:
        test_id: Test identifier (e.g., "PER-1").
        archivo_name: Recording filename from Humyn (e.g., "Spanish_Peru_1.wav").
        turns_df: Full Humyn turns DataFrame.
        verbose: If True, log detailed steps.
        dry_run: If True, validate contracts without running Whisper.
        
    Returns:
        Result dict with metadata.
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"Testing: {test_id} ({archivo_name})")
    logger.info(f"{'='*70}")
    
    # Filter for this recording
    recording_turns = turns_df[turns_df["archivo"] == archivo_name].copy()
    if recording_turns.empty:
        raise ValueError(f"No turns found for {archivo_name}")
    
    n_turns = len(recording_turns)
    n_speakers = len(recording_turns["hablante"].unique())
    duration_s = recording_turns["fin"].max()
    
    logger.info(f"Recording: {n_turns} turns, {n_speakers} speakers, {duration_s:.1f}s")
    
    # Create output directory
    output_dir = OUTPUT_BASE / test_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    audio_path = output_dir / "audio.wav"
    diarization_path = output_dir / "diarization.json"
    transcription_path = output_dir / "transcription.json"
    words_path = output_dir / "whisper_words.json"
    
    # Extract audio from Humyn parquet
    if verbose:
        logger.info(f"Extracting audio from Humyn parquet...")
    
    # Find the recording in Humyn parquet and extract audio
    audio_found = False
    for pf in HUMYN_PARQUET_RAW:
        table = pq.read_table(pf)
        df_chunk = table.to_pandas()
        matching = df_chunk[df_chunk["file_name"] == archivo_name]
        
        if not matching.empty:
            audio_bytes = matching.iloc[0]["audio"]["bytes"]
            extract_audio_to_wav(audio_bytes, audio_path)
            audio_found = True
            if verbose:
                logger.info(f"Audio extracted: {audio_path.name}")
            break
    
    if not audio_found:
        raise FileNotFoundError(f"Could not find audio for {archivo_name} in Humyn parquet")
    
    # Convert Humyn turns to diarization.json
    if verbose:
        logger.info(f"Converting Humyn turns to diarization.json...")
    
    diarization = humyn_turns_to_diarization(recording_turns, recording_id=test_id)
    skip_count = diarization.pop("metadata", {}).get("skipped_zero_duration", 0)
    if skip_count > 0 and verbose:
        logger.warning(f"Skipped {skip_count} zero-duration turns (data quality issue in Humyn)")
    
    # Validate diarization
    try:
        validate_diarization_contract(diarization)
        if verbose:
            logger.info(f"Diarization validated: {len(diarization['segments'])} segments")
    except ValueError as e:
        raise ValueError(f"Diarization validation failed: {e}")
    
    # Save diarization
    with open(diarization_path, "w", encoding="utf-8") as f:
        json.dump(diarization, f, indent=2, ensure_ascii=False)
    logger.info(f"Diarization saved: {diarization_path}")
    
    # Run ASR
    if verbose:
        logger.info(f"Running ASR pipeline...")
    
    result = process_asr(
        audio_path=audio_path,
        diarization_path=diarization_path,
        output_path=transcription_path,
        words_path=words_path,
        model_size="base",
        verbose=verbose,
        dry_run=dry_run
    )
    
    logger.info(f"✓ {test_id} complete")
    logger.info(f"  Device: {result['device']}")
    logger.info(f"  Segments: {result['segments_count']}")
    logger.info(f"  Output: {transcription_path}")
    
    return {
        "test_id": test_id,
        "archivo": archivo_name,
        "humyn_turns": n_turns,
        "speakers": n_speakers,
        "duration_s": duration_s,
        "output_segments": result["segments_count"],
        "status": result["status"]
    }


def main(verbose: bool = False, dry_run: bool = False) -> None:
    """Main test runner."""
    logger.info(f"Loading Humyn normalized turns from: {HUMYN_TURNOS}")
    
    if not HUMYN_TURNOS.exists():
        raise FileNotFoundError(f"Humyn turnos not found: {HUMYN_TURNOS}")
    
    # Load normalized turns (already preprocessed)
    turns_df = pq.read_table(str(HUMYN_TURNOS)).to_pandas()
    logger.info(f"Loaded {len(turns_df)} total turns from Humyn")
    
    # Load raw Humyn parquet for audio extraction
    logger.info(f"Loading raw Humyn audio from: {HUMYN_CACHE}")
    humyn_raw_parquets = list(HUMYN_CACHE.glob("*.parquet"))
    if not humyn_raw_parquets:
        raise FileNotFoundError(f"No Humyn parquet files found in {HUMYN_CACHE}")
    
    # Run tests
    results = []
    for test_id, archivo_name in PER_RECORDINGS.items():
        try:
            result = test_recording(
                test_id=test_id,
                archivo_name=archivo_name,
                turns_df=turns_df,
                verbose=verbose,
                dry_run=dry_run
            )
            results.append(result)
        except Exception as e:
            logger.error(f"✗ {test_id} FAILED: {e}")
            results.append({
                "test_id": test_id,
                "status": f"failed: {e}"
            })
    
    # Summary
    logger.info(f"\n{'='*70}")
    logger.info("Summary:")
    logger.info(f"{'='*70}")
    for result in results:
        status_icon = "✓" if "success" in result.get("status", "") or "dry-run" in result.get("status", "") else "✗"
        logger.info(f"{status_icon} {result['test_id']}: {result.get('status', 'unknown')}")
        if "output_segments" in result:
            logger.info(f"   Turns: {result['humyn_turns']} → Segments: {result['output_segments']}")
    
    logger.info(f"{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test ASR on Humyn LATAM Peruvian recordings"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate contracts without running Whisper (fast test)"
    )
    
    args = parser.parse_args()
    
    try:
        main(verbose=args.verbose, dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
