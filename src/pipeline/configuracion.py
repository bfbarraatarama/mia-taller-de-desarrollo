"""Parámetros públicos de la ejecución de una reunión (sin dependencias de Qt)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..minutas.generacion import ConfiguracionMinutas
from ..rutas import DIRECTORIO_RESULTADOS_PREDETERMINADO, directorio_reunion


@dataclass(frozen=True)
class SolicitudReunion:
    fuentes: tuple[str | Path, ...]
    salida: str | Path = DIRECTORIO_RESULTADOS_PREDETERMINADO
    dispositivo_diarizacion: str = 'auto'
    num_speakers: int | None = None
    modelo_stt: str = 'medium'
    dispositivo_stt: str | None = None
    minutas: ConfiguracionMinutas = field(default_factory=ConfiguracionMinutas)
    identificacion: str = 'omitir'  # 'pausa' para GUI, 'omitir' para Python/CLI

    def __post_init__(self):
        if not self.fuentes:
            raise ValueError('Se requiere uno o más archivos de entrada.')
        object.__setattr__(self, 'salida', directorio_reunion(self.salida, fuentes=self.fuentes))
        if self.identificacion not in {'pausa', 'omitir'}:
            raise ValueError('identificacion debe ser pausa u omitir.')
        if self.dispositivo_diarizacion not in {'auto', 'cpu', 'cuda'}:
            raise ValueError('Dispositivo de diarización inválido.')
        if self.dispositivo_stt not in {None, 'cpu', 'cuda'}:
            raise ValueError('Dispositivo STT inválido.')
        if not self.modelo_stt or not self.modelo_stt.strip():
            raise ValueError('El modelo Whisper debe ser no vacío.')
        if self.num_speakers is not None and (isinstance(self.num_speakers, bool) or self.num_speakers < 1):
            raise ValueError('num_speakers debe ser entero positivo.')
