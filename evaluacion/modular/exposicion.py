"""Informe de exposición previa de la muestra (requisito «Informe de exposición previa»).

Combina la declaración versionada de `exposicion.toml` con las exclusiones del manifiesto. Cada fuente de la
muestra tiene que declarar su uso en el desarrollo y su exposición frente a los modelos de los módulos que alimenta.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

EXPOSICION = Path(__file__).resolve().parent / "exposicion.toml"
MODELO_DEL_MODULO = {"stt": "whisper", "diarizacion": "pyannote", "minutas": "qwen"}  # la asociación no usa modelos


class ExposicionIncompleta(Exception):
    """Falta declarar una fuente de la muestra o un modelo de sus módulos."""


def informe_exposicion(manifiesto: dict, ruta: Path = EXPOSICION) -> dict:
    with open(ruta, "rb") as f:
        declarado = tomllib.load(f)
    elementos = manifiesto["contenido"]["elementos"]
    fuentes, faltas = {}, []
    for fuente in sorted({e["fuente"] for e in elementos}):
        propios = [e for e in elementos if e["fuente"] == fuente]
        modulos = sorted({m for e in propios for m in e["modulos"]})
        modelos = sorted({MODELO_DEL_MODULO[m] for m in modulos if m in MODELO_DEL_MODULO})
        d = declarado.get("fuentes", {}).get(fuente)
        if d is None:
            faltas.append(f"{fuente}: falta declarar la fuente")
            continue
        faltas += [f"{fuente}: falta declarar la exposición frente a {m}" for m in modelos
                   if m not in d.get("entrenamiento", {})]
        if "desarrollo" not in d:
            faltas.append(f"{fuente}: falta declarar su uso en el desarrollo")
        fuentes[fuente] = {"elementos": len(propios), "modulos": modulos, "desarrollo": d.get("desarrollo"),
                           "entrenamiento": {m: d.get("entrenamiento", {}).get(m) for m in modelos}}
    if faltas:
        raise ExposicionIncompleta(f"{Path(ruta).name} incompleto: " + "; ".join(faltas))
    excluidos = {s: {"motivo": motivo, "en_la_muestra": False}
                 for s, motivo in manifiesto["contenido"]["exclusiones"].items()}
    pendientes = [f"{f}: desarrollo" for f, d in fuentes.items() if d["desarrollo"]["estado"] == "a confirmar"]
    pendientes += [f"{f}: {m}" for f, d in fuentes.items() for m, v in d["entrenamiento"].items()
                   if v["estado"] == "a confirmar"]
    return {"modelos": declarado["modelos"], "fuentes": fuentes, "excluidos": excluidos, "pendientes": pendientes,
            "contenido_sha256_muestra": manifiesto["contenido_sha256"]}
