"""Renderización determinista de reportes guardados."""

from __future__ import annotations

import json
from pathlib import Path

from .archivos import leer_json


def escribir_markdown(origen: Path, destino: Path) -> None:
    datos = leer_json(origen)
    contenido = json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True)
    with destino.open("x", encoding="utf-8", newline="\n") as f:
        f.write("# Reporte de evaluación\n\n```json\n" + contenido + "\n```\n")
