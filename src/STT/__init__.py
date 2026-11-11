"""
Stage 3: Speech-to-text (STT).

Convert audio.wav -> asr.json. Speaker association is Stage 4.
"""

from .asr_core import (
    build_asr,
    free_gpu_memory,
    get_device,
    load_whisper_model,
    process_asr,
    transcribe_audio,
    validate_asr_contract,
)

__all__ = [
    "build_asr",
    "free_gpu_memory",
    "get_device",
    "load_whisper_model",
    "process_asr",
    "transcribe_audio",
    "validate_asr_contract",
]
