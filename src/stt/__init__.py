"""API pública de STT, conservada con carga diferida de Whisper.

La carga diferida permite inspeccionar el paquete y usar --help en entornos
sin el modelo instalado; al invocar STT se requieren sus dependencias reales.
"""

from importlib import import_module

__all__ = [
    "build_asr", "free_gpu_memory", "get_device", "load_whisper_model",
    "process_asr", "transcribe_audio", "validate_asr_contract",
]


def __getattr__(nombre: str):
    if nombre in __all__:
        return getattr(import_module('.asr_core', __name__), nombre)
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")
