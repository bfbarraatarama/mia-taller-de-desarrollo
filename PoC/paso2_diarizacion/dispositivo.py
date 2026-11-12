"""Selección del dispositivo (design.md §6). Sin paso automático a CPU si se pidió CUDA."""

from __future__ import annotations

from errores import DiarizacionError

MODOS = ("auto", "cpu", "cuda")


def elegir_dispositivo(modo: str = "auto") -> str:
    """`auto`: CUDA si está disponible, si no CPU. `cpu`: siempre CPU. `cuda`: error si no hay CUDA."""
    if modo not in MODOS:
        raise DiarizacionError("parametros", f"Modo de dispositivo desconocido: {modo!r} (opciones: {', '.join(MODOS)})")
    if modo == "cpu":
        return "cpu"
    try:
        import torch
    except ImportError:
        raise DiarizacionError("dispositivo", "PyTorch no está instalado en este entorno. Ver README, "
                                              "sección Instalación.") from None
    disponible = bool(torch.cuda.is_available())
    if modo == "cuda" and not disponible:
        raise DiarizacionError(
            "dispositivo",
            f"Se pidió --device cuda pero no hay CUDA disponible (torch {torch.__version__}). En una máquina con "
            "GPU instalá el wheel cu128 de PyTorch (ver README); si no, usá --device cpu o --device auto.")
    return "cuda" if disponible else "cpu"
