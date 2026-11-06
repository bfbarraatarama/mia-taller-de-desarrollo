"""Adaptador del contrato externo transcription.json a intervenciones internas."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .contratos import Intervencion


def leer_transcripcion(origen: str | Path | Mapping[str, Any]) -> tuple[list[Intervencion], bytes]:
    """Devuelve intervenciones cronológicas y bytes canónicos para trazabilidad."""
    if isinstance(origen, (str, Path)):
        datos_bytes = Path(origen).read_bytes()
        datos = json.loads(datos_bytes)
    elif isinstance(origen, Mapping):
        datos = dict(origen)
        datos_bytes = json.dumps(datos, ensure_ascii=False, sort_keys=True).encode("utf-8")
    else:
        raise TypeError("La transcripción debe ser una ruta o un objeto JSON.")

    if not isinstance(datos, dict) or not isinstance(datos.get("segments"), list):
        raise ValueError("La transcripción debe contener una lista 'segments'.")
    if not datos["segments"]:
        raise ValueError("La transcripción no contiene intervenciones.")

    filas: list[tuple[int, dict[str, Any]]] = []
    for indice, fila in enumerate(datos["segments"]):
        if not isinstance(fila, dict):
            raise ValueError(f"La intervención {indice + 1} no es un objeto JSON.")
        filas.append((indice, fila))

    # Valida antes de ordenar; evita comparar valores heterogéneos con sort().
    preparadas: list[tuple[int, Intervencion]] = []
    for indice, fila in filas:
        try:
            intervencion = Intervencion(
                id="temporal", inicio=fila["start"], fin=fila["end"],
                hablante=fila.get("speaker"), nombre=fila.get("name"),
                texto=fila["text"], superposicion=fila["overlap"],
                ambiguo=fila["ambiguous"],
            )
        except (KeyError, ValidationError, ValueError, TypeError) as exc:
            raise ValueError(f"Intervención {indice + 1} inválida: {exc}") from exc
        preparadas.append((indice, intervencion))

    preparadas.sort(key=lambda x: (x[1].inicio, x[0]))
    intervenciones = [
        intervencion.model_copy(update={"id": f"I{numero:06d}"})
        for numero, (_, intervencion) in enumerate(preparadas, start=1)
    ]
    return intervenciones, datos_bytes


def representar_intervenciones(intervenciones: list[Intervencion]) -> str:
    """El modelo solo recibe claves y contenido semántico en español."""
    return json.dumps(
        {"intervenciones": [intervencion.model_dump() for intervencion in intervenciones]},
        ensure_ascii=False, separators=(",", ":"),
    )