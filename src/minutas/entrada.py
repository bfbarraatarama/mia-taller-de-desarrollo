"""Adaptador del contrato externo transcription.json a intervenciones internas."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .contratos import Intervencion


def leer_transcripcion(origen: str | Path | Mapping[str, Any]) -> tuple[list[Intervencion], bytes]:
    """Devuelve intervenciones en orden de reconocimiento (cronológico en el contrato histórico)."""
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
    actual = any(any(k in fila for k in ("timing", "source", "speakers_detected")) for _, fila in filas)
    if actual:
        from ..asociacion.contrato import validar_transcripcion
        etiquetas = {f["speaker"] for _, f in filas if isinstance(f.get("speaker"), str)}
        etiquetas.update(d["speaker"] for _, f in filas if isinstance(f.get("speakers_detected"), list)
                         for d in f["speakers_detected"] if isinstance(d, dict) and isinstance(d.get("speaker"), str))
        if validar_transcripcion(datos, float("inf"), etiquetas):
            raise ValueError("La transcripción no cumple el contrato de asociación.")
    preparadas: list[tuple[int, Intervencion]] = []
    for indice, fila in filas:
        try:
            intervencion = Intervencion(
                id="temporal", inicio=fila["start"], fin=fila["end"],
                hablante=fila.get("speaker"), nombre=fila.get("name"),
                texto=fila["text"], superposicion=fila["overlap"],
                ambiguo=fila["ambiguous"],
                resolucion_temporal={"word": "palabra", "segment": "segmento", "unknown": "desconocida"}.get(fila.get("timing")),
                hablantes_detectados=[{"hablante": d["speaker"], "nombre": d["name"]}
                                     for d in fila["speakers_detected"]] if fila.get("speakers_detected") is not None else None,
            )
        except (KeyError, ValidationError, ValueError, TypeError) as exc:
            # No reproducir los campos de entrada en errores que puede persistir el orquestador.
            raise ValueError(f"Intervención {indice + 1} inválida ({type(exc).__name__}).") from None
        preparadas.append((indice, intervencion))

    if not actual:
        preparadas.sort(key=lambda x: (x[1].inicio, x[0]))
    intervenciones = [
        intervencion.model_copy(update={"id": f"I{numero:06d}"})
        for numero, (_, intervencion) in enumerate(preparadas, start=1)
    ]
    return intervenciones, datos_bytes


def representar_intervenciones(intervenciones: list[Intervencion]) -> str:
    """El modelo solo recibe claves y contenido semántico en español."""
    return json.dumps(
        {"intervenciones": [intervencion.model_dump(exclude={"resolucion_temporal", "hablantes_detectados"}
                         if intervencion.resolucion_temporal is None else None) for intervencion in intervenciones]},
        ensure_ascii=False, separators=(",", ":"),
    )