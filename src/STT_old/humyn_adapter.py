"""
Adapter: Convert Humyn LATAM turn-based format to diarization.json contract.

Humyn data is turn-based (each turn = one speaker interval).
This adapter creates one diarization segment per turn.
"""

from __future__ import annotations

from typing import Optional
import pandas as pd


def humyn_turns_to_diarization(
    turns_df: pd.DataFrame,
    recording_id: Optional[str] = None
) -> dict:
    """
    Convert Humyn turn-based data to diarization.json contract.
    
    Args:
        turns_df: DataFrame with columns:
            - archivo: recording filename
            - hablante: speaker name (e.g., "Speaker A")
            - inicio: start time in seconds
            - fin: end time in seconds
        recording_id: For logging/context (optional).
        
    Returns:
        Dict conforming to diarization.json contract:
        {"segments": [{"start": float, "end": float, "speaker": str}, ...]}
        
    Raises:
        ValueError: If DataFrame structure or data invalid.
    """
    if turns_df.empty:
        raise ValueError("turns_df cannot be empty")
    
    required_cols = {"hablante", "inicio", "fin"}
    if not required_cols.issubset(turns_df.columns):
        raise ValueError(f"DataFrame must have columns: {required_cols}")
    
    # Get unique speakers and map to SPEAKER_00, SPEAKER_01, etc.
    unique_speakers = sorted(turns_df["hablante"].unique())
    speaker_mapping = {
        orig_speaker: f"SPEAKER_{i:02d}"
        for i, orig_speaker in enumerate(unique_speakers)
    }
    
    # Build segments: one per turn
    segments = []
    skipped = 0
    for _, row in turns_df.iterrows():
        start = row["inicio"]
        end = row["fin"]
        original_speaker = row["hablante"]
        
        # Validate timing
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise ValueError(f"Timing must be numeric; got {type(start).__name__}, {type(end).__name__}")
        
        if start < 0 or end < 0:
            raise ValueError(f"Timing cannot be negative: start={start}, end={end}")
        
        # Skip zero-duration turns (data quality issue in Humyn)
        if start >= end:
            skipped += 1
            continue
        
        # Map to contract speaker label
        speaker = speaker_mapping[original_speaker]
        
        segments.append({
            "start": float(start),
            "end": float(end),
            "speaker": speaker
        })
    
    return {"segments": segments, "metadata": {"skipped_zero_duration": skipped}}
