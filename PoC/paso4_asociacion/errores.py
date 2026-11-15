"""Error único de la Etapa 4: lleva el paso en que falló. Quien la invoca decide por esta excepción
(o por el código de salida del CLI), nunca por la presencia de `transcription.json`."""

from __future__ import annotations

from pathlib import Path

PASOS = ("parametros", "audio", "diarizacion", "asr", "contrato", "escritura", "interno")


class AsociacionError(Exception):
    def __init__(self, paso: str, mensaje: str, *, archivo: str | Path | None = None,
                 violaciones: list[str] | None = None):
        if paso not in PASOS:
            raise ValueError(f"Paso desconocido: {paso}")
        super().__init__(mensaje)
        self.paso = paso
        self.mensaje = mensaje
        self.archivo = str(archivo) if archivo is not None else None
        self.violaciones = list(violaciones or [])
