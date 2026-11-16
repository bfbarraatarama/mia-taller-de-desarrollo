"""Error único de la Etapa 2: lleva la etapa del flujo en que falló (design.md §3 y §5)."""

from __future__ import annotations

ETAPAS = ("parametros", "audio", "token", "dispositivo", "modelo", "decodificacion",
          "ejecucion", "contrato", "escritura")


class DiarizacionError(Exception):
    """Fallo de una ejecución. El orquestador decide por esta excepción (o por el código de salida),
    nunca por la presencia de `diarization.json`."""

    def __init__(self, etapa: str, mensaje: str, tipo: str | None = None):
        if etapa not in ETAPAS:
            raise ValueError(f"Etapa desconocida: {etapa}")
        super().__init__(mensaje)
        self.etapa = etapa
        self.mensaje = mensaje
        self.tipo = tipo or "DiarizacionError"
        self.archivo_error = None  # ruta de diarization.error.json, si se escribió
