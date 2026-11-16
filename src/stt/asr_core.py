"""
Core STT (speech-to-text) implementation for Stage 3.

Converts audio.wav -> asr.json, following hito-3/pipeline-etapas-y-herramientas.md.
This stage does not use the diarization: speaker association is Stage 4.
"""

from __future__ import annotations

import gc
import json
import logging
import traceback
from pathlib import Path

import torch
import whisper

from .contrato import LANGUAGE, DURATION_TOLERANCE_S, build_asr, validate_asr_contract

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_MODEL_SIZE = "medium"
SAMPLE_RATE = 16000  # Whisper standard

def get_device(verbose: bool = False) -> str:
    """Return 'cuda' if a GPU is available, else 'cpu'."""
    try:
        if torch.cuda.is_available():
            if verbose:
                logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
            return "cuda"
        if verbose:
            logger.info("No GPU detected; using CPU")
    except Exception as e:
        if verbose:
            logger.warning(f"GPU check failed ({e}); falling back to CPU")
    return "cpu"


def load_whisper_model(
    model_size: str = DEFAULT_MODEL_SIZE,
    device: str = "cpu",
    verbose: bool = False,
) -> whisper.Whisper:
    """
    Load a Whisper model.

    The model is not cached: the caller owns the only reference, so dropping it
    and calling free_gpu_memory() actually releases the GPU for the next stage.
    """
    if verbose:
        logger.info(f"Loading Whisper model ({model_size}, device: {device})...")
    return whisper.load_model(model_size, device=device)


def free_gpu_memory() -> None:
    """Collect unreferenced objects and return cached CUDA memory to the driver."""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def transcribe_audio(
    audio_path: str | Path,
    model: whisper.Whisper,
    language: str = LANGUAGE,
    verbose: bool = False,
) -> dict:
    """
    Transcribe the whole audio at once with word-level timestamps.

    The audio is not split by segment: Whisper loses context and tends to
    invent text on short fragments.
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
        verbose=verbose,
    )

    if verbose:
        logger.info(f"Transcription complete. Segments: {len(result['segments'])}")

    return result


def process_asr(
    audio_path: str | Path,
    output_path: str | Path,
    model_size: str = DEFAULT_MODEL_SIZE,
    verbose: bool = False,
    dry_run: bool = False,
    device: str | None = None,
) -> dict:
    """
    Main STT pipeline: audio.wav -> asr.json.

    Args:
        audio_path: Path to normalized WAV file.
        output_path: Path to write asr.json.
        model_size: Whisper model size ("medium" by default; "small" is the
            memory fallback).
        verbose: If True, log processing steps.
        dry_run: If True, only check the audio can be read; skip Whisper.
        device: "cuda" or "cpu". Auto-detected when None.

    Returns:
        Metadata dict with {"model", "device", "duration", "segments_count", "status"}.

    Raises:
        FileNotFoundError: If the audio file is missing.
        ValueError: If the output does not satisfy the contract.
    """
    audio_path = Path(audio_path)
    output_path = Path(output_path)

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if verbose:
        logger.info(f"Processing: {audio_path.name}")

    audio_duration = len(whisper.load_audio(str(audio_path))) / SAMPLE_RATE
    if verbose:
        logger.info(f"Audio duration: {audio_duration:.2f}s")

    if dry_run:
        return {
            "model": model_size,
            "device": "N/A (dry-run)",
            "duration": audio_duration,
            "segments_count": 0,
            "status": "dry-run (audio readable)",
        }

    if device is None:
        device = get_device(verbose=verbose)
    model = load_whisper_model(model_size=model_size, device=device, verbose=verbose)

    try:
        result = transcribe_audio(audio_path, model, language=LANGUAGE, verbose=verbose)
        asr = build_asr(result, language=LANGUAGE)
        validate_asr_contract(asr, audio_duration)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asr, f, indent=2, ensure_ascii=False)

        if verbose:
            logger.info(f"ASR saved: {output_path}")

        return {
            "model": model_size,
            "device": device,
            "duration": audio_duration,
            "segments_count": len(asr["segments"]),
            "status": "success",
        }
    except BaseException as e:
        # Frames kept alive by the traceback would still reference the model.
        traceback.clear_frames(e.__traceback__)
        raise
    finally:
        del model
        free_gpu_memory()
        if verbose:
            logger.info("Whisper model released and GPU memory freed")
