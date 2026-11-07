"""
Core ASR (Automatic Speech Recognition) implementation for Stage 3.

Converts audio + diarization → transcription.json, following feli.md contracts.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Optional
import gc

import torch
try:
    import whisper_timestamped as whisper
except ImportError:
    import whisper

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_MODEL_CACHE = {}


def get_device(verbose: bool = False) -> str:
    """
    Auto-detect GPU availability; return 'cuda' or 'cpu'.
    
    Args:
        verbose: If True, log device selection.
        
    Returns:
        'cuda' if CUDA available, else 'cpu'.
    """
    try:
        if torch.cuda.is_available():
            device = "cuda"
            if verbose:
                logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
        else:
            device = "cpu"
            if verbose:
                logger.info("No GPU detected; using CPU")
    except Exception as e:
        device = "cpu"
        if verbose:
            logger.warning(f"GPU check failed ({e}); falling back to CPU")
    return device


def load_whisper_model(
    model_size: str = "base",
    device: str = "cpu",
    verbose: bool = False
) -> whisper.Whisper:
    """
    Load Whisper model with caching. Only one model size cached at a time.
    
    Args:
        model_size: Model size ("tiny", "base", "small", "medium", "large").
        device: Device to load on ("cuda" or "cpu").
        verbose: If True, log loading steps.
        
    Returns:
        Loaded Whisper model.
    """
    # Unload other cached models to free memory
    for cached_size in list(_MODEL_CACHE.keys()):
        if cached_size != model_size:
            if verbose:
                logger.info(f"Unloading Whisper model ({cached_size}) to free memory")
            del _MODEL_CACHE[cached_size]
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    if model_size not in _MODEL_CACHE:
        if verbose:
            logger.info(f"Loading Whisper model ({model_size}, device: {device})...")
        _MODEL_CACHE[model_size] = whisper.load_model(model_size, device=device)
    else:
        if verbose:
            logger.info(f"Cache-loading Whisper model ({model_size})")
    
    return _MODEL_CACHE[model_size]


def transcribe_audio(
    audio_path: str | Path,
    model: whisper.Whisper,
    language: str = "es",
    verbose: bool = False
) -> dict:
    """
    Transcribe audio file using Whisper with word-level timestamps.
    
    Args:
        audio_path: Path to WAV file.
        model: Loaded Whisper model.
        language: Language code (e.g., "es" for Spanish).
        verbose: If True, log transcription steps.
        
    Returns:
        Whisper result dict with word-level timing.
        Structure: {"segments": [{"id", "seek", "start", "end", "text", "words": [...]}, ...], ...}
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    if verbose:
        logger.info(f"Transcribing audio: {audio_path.name}")
    
    result = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=True,
        verbose=verbose
    )
    
    if verbose:
        logger.info(f"Transcription complete. Segments: {len(result['segments'])}")
    
    return result


def validate_diarization_contract(diarization: dict) -> None:
    """
    Validate diarization.json structure against contract.
    
    Args:
        diarization: Dict with structure {"segments": [...]}.
        
    Raises:
        ValueError: If structure or semantics invalid.
    """
    if not isinstance(diarization, dict):
        raise ValueError("Diarization must be a dict")
    
    if "segments" not in diarization:
        raise ValueError("Diarization must have 'segments' key")
    
    segments = diarization["segments"]
    if not isinstance(segments, list):
        raise ValueError("'segments' must be a list")
    
    if not segments:
        raise ValueError("'segments' cannot be empty")
    
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            raise ValueError(f"Segment {i} must be a dict")
        
        for key in ["start", "end", "speaker"]:
            if key not in seg:
                raise ValueError(f"Segment {i} missing '{key}'")
        
        start = seg["start"]
        end = seg["end"]
        
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise ValueError(f"Segment {i}: 'start' and 'end' must be numeric")
        
        if not (math.isfinite(start) and math.isfinite(end)):
            raise ValueError(f"Segment {i}: 'start' and 'end' must be finite")
        
        if start < 0 or end < 0:
            raise ValueError(f"Segment {i}: times cannot be negative")
        
        if start >= end:
            raise ValueError(f"Segment {i}: start ({start}) must be < end ({end})")
        
        speaker = seg["speaker"]
        if not isinstance(speaker, str) or not speaker.strip():
            raise ValueError(f"Segment {i}: 'speaker' must be non-empty string")


def validate_transcription_contract(transcription: dict, audio_duration: float) -> None:
    """
    Validate transcription.json structure against contract.
    
    Args:
        transcription: Dict with structure {"segments": [...]}.
        audio_duration: Duration of audio in seconds.
        
    Raises:
        ValueError: If structure or semantics invalid.
    """
    if not isinstance(transcription, dict):
        raise ValueError("Transcription must be a dict")
    
    if "segments" not in transcription:
        raise ValueError("Transcription must have 'segments' key")
    
    segments = transcription["segments"]
    if not isinstance(segments, list):
        raise ValueError("'segments' must be a list")
    
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            raise ValueError(f"Segment {i} must be a dict")
        
        for key in ["start", "end", "speaker", "text"]:
            if key not in seg:
                raise ValueError(f"Segment {i} missing '{key}'")
        
        start = seg["start"]
        end = seg["end"]
        text = seg["text"]
        speaker = seg["speaker"]
        
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise ValueError(f"Segment {i}: 'start' and 'end' must be numeric")
        
        if not (math.isfinite(start) and math.isfinite(end)):
            raise ValueError(f"Segment {i}: 'start' and 'end' must be finite")
        
        if start < 0 or end < 0:
            raise ValueError(f"Segment {i}: times cannot be negative")
        
        if start >= end:
            raise ValueError(f"Segment {i}: start must be < end")
        
        if end > audio_duration:
            raise ValueError(f"Segment {i}: end ({end}) exceeds audio duration ({audio_duration})")
        
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Segment {i}: 'text' must be non-empty string")
        
        if not isinstance(speaker, str) or not speaker.strip():
            raise ValueError(f"Segment {i}: 'speaker' must be non-empty string")


def associate_speakers(
    words: list[dict],
    diarization: dict,
    verbose: bool = False
) -> list[dict]:
    """
    For each diarization segment, assign all Whisper words whose start time falls 
    within [segment.start, segment.end) to that segment.
    
    Args:
        words: List of word dicts from Whisper, each with {"word", "start", "end"}.
        diarization: Diarization contract dict.
        verbose: If True, log association steps.
        
    Returns:
        List of output segments with {"start", "end", "speaker", "text"}.
    """
    if not words:
        return []
    
    diar_segments = diarization["segments"]
    
    # Filter out invalid words and sort by start time
    valid_words = []
    for word in words:
        w_start = word.get("start")
        w_end = word.get("end")
        w_text = word.get("word", "").strip()
        
        if not w_text:
            continue
        
        # Skip words with invalid timing
        if not isinstance(w_start, (int, float)) or not isinstance(w_end, (int, float)):
            continue
        
        if not (math.isfinite(w_start) and math.isfinite(w_end)):
            continue
        
        if w_start >= w_end:
            continue
        
        valid_words.append(word)
    
    # Sort by start time to ensure chronological order
    valid_words.sort(key=lambda w: w["start"])
    
    # For each diarization segment, find words whose start time is within [start, end)
    output_segments = []
    
    for diar_seg in diar_segments:
        seg_start = diar_seg["start"]
        seg_end = diar_seg["end"]
        speaker = diar_seg["speaker"]
        
        # Words whose start time is in [seg_start, seg_end) belong to this segment
        segment_words = [
            word["word"].strip()
            for word in valid_words
            if seg_start <= word["start"] < seg_end
        ]
        
        if segment_words:
            output_segments.append({
                "start": seg_start,
                "end": seg_end,
                "speaker": speaker,
                "text": " ".join(segment_words)
            })
            
            if verbose:
                print(f"  Segment {speaker} [{seg_start:.1f}-{seg_end:.1f}s]: {len(segment_words)} words")
    
    if verbose:
        logger.info(f"Matched {len(valid_words)} words into {len(output_segments)} segments by diarization")
    
    return output_segments


def process_asr(
    audio_path: str | Path,
    diarization_path: str | Path,
    output_path: str | Path,
    model_size: str = "large-v2",
    verbose: bool = False,
    dry_run: bool = False,
    words_path: str | Path | None = None
) -> dict:
    """
    Main ASR pipeline: audio + diarization → transcription.json.
    
    Args:
        audio_path: Path to normalized WAV file.
        diarization_path: Path to diarization.json.
        output_path: Path to write transcription.json.
        model_size: Whisper model size.
        verbose: If True, log processing steps.
        dry_run: If True, validate contracts but don't run Whisper.
        words_path: If given, also write the raw Whisper word list here
            ({"words": [{"start", "end", "word"}, ...]}) before speaker association.
        
    Returns:
        Metadata dict with {"model", "device", "duration", "segments_count", ...}.
        
    Raises:
        FileNotFoundError: If input files missing.
        ValueError: If contract validation fails.
    """
    audio_path = Path(audio_path)
    diarization_path = Path(diarization_path)
    output_path = Path(output_path)
    
    # Validate inputs
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    if not diarization_path.exists():
        raise FileNotFoundError(f"Diarization file not found: {diarization_path}")
    
    if verbose:
        logger.info(f"Processing: {audio_path.name}")
        logger.info(f"Diarization: {diarization_path.name}")
        logger.info(f"Output: {output_path.name}")
    
    # Load and validate diarization
    with open(diarization_path, encoding="utf-8") as f:
        diarization = json.load(f)
    
    validate_diarization_contract(diarization)
    
    if verbose:
        logger.info(f"Diarization validated: {len(diarization['segments'])} segments")
    
    # Get audio duration (via Whisper's loader)
    audio_data = whisper.load_audio(str(audio_path))
    sample_rate = 16000  # Whisper standard
    audio_duration = len(audio_data) / sample_rate
    
    if verbose:
        logger.info(f"Audio duration: {audio_duration:.2f}s")
    
    # DRY RUN: validate contracts and exit
    if dry_run:
        if verbose:
            logger.info("DRY RUN: Contract validation passed. Skipping Whisper transcription.")
        return {
            "model": model_size,
            "device": "N/A (dry-run)",
            "duration": audio_duration,
            "segments_count": 0,
            "status": "dry-run (validation passed)"
        }
    
    # Detect device and load model
    device = get_device(verbose=verbose)
    model = load_whisper_model(model_size=model_size, device=device, verbose=verbose)
    
    try:
        # Transcribe (hardcoded to Spanish)
        result = transcribe_audio(audio_path, model, language="es", verbose=verbose)
        
        # Extract words and associate with speakers
        all_words = []
        for seg in result.get("segments", []):
            if "words" in seg:
                all_words.extend(seg["words"])
        
        if words_path is not None:
            words_path = Path(words_path)
            words_path.parent.mkdir(parents=True, exist_ok=True)
            with open(words_path, "w", encoding="utf-8") as f:
                json.dump({"words": all_words}, f, ensure_ascii=False)
            if verbose:
                logger.info(f"Raw Whisper words saved: {words_path} ({len(all_words)} words)")
        
        output_segments = associate_speakers(all_words, diarization, verbose=verbose)
        
        # Validate output
        validate_transcription_contract(
            {"segments": output_segments},
            audio_duration
        )
        
        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"segments": output_segments}, f, indent=2, ensure_ascii=False)
        
        if verbose:
            logger.info(f"Transcription saved: {output_path}")
        
        return {
            "model": model_size,
            "device": device,
            "duration": audio_duration,
            "segments_count": len(output_segments),
            "status": "success"
        }
    
    finally:
        # Free GPU memory
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if verbose:
            logger.info("GPU memory freed")
