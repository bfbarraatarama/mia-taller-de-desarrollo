"""
Stage 3: Automatic Speech Recognition (ASR).

Convert audio + diarization → transcription.json.
"""

from .asr_core import (
    associate_speakers,
    get_device,
    load_whisper_model,
    process_asr,
    transcribe_audio,
    validate_diarization_contract,
    validate_transcription_contract,
)
from .humyn_adapter import humyn_turns_to_diarization

__all__ = [
    "associate_speakers",
    "get_device",
    "load_whisper_model",
    "process_asr",
    "transcribe_audio",
    "validate_diarization_contract",
    "validate_transcription_contract",
    "humyn_turns_to_diarization",
]
