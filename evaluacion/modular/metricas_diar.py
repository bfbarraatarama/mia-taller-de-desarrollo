"""DER y JER de la diarización en Figshare, sin umbral (requisito «Métricas de diarización», D10).

Misma configuración que la evaluación de S26 de la Etapa 2, sin copiar su código: la referencia de cada tarea se
arma con `leer_anotacion` y `construir` (política de `politica_etiquetas.json`) y las métricas con
`der.Evaluador` (DER estricto, DER con tolerancia NIST de ±0,25 s y JER, con habla superpuesta).
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from pathlib import Path

from evaluacion.diarizacion import der
from evaluacion.diarizacion.preparar_figshare import leer_anotacion
from evaluacion.diarizacion.referencia import POLITICA_JSON, construir, leer_politica

from .audio import FS, leer_miembro


def referencia_tarea(elemento: dict, cache: Path) -> list[dict]:
    """Segmentos de referencia [{start, end, speaker}] de una tarea de Figshare, verificando sus frases."""
    ref, anotaciones = elemento["referencia"], {}
    with tempfile.TemporaryDirectory() as tmp:
        for entrada, esperado in sorted(ref["entradas"].items()):
            datos = leer_miembro(Path(cache) / ref["original"], entrada)
            if hashlib.sha256(datos).hexdigest() != esperado:
                raise ValueError(f"{entrada}: la referencia no coincide con el SHA-256 del manifiesto")
            ruta = Path(tmp) / Path(entrada).name
            ruta.write_bytes(datos)
            anotaciones[int(re.search(r"channel(\d+)", entrada).group(1))] = leer_anotacion(ruta)
    return construir(anotaciones, elemento["cuadros"], FS, leer_politica(), sesion=elemento["sesion"])["segmentos"]


def metricas_diarizacion(elementos: list[dict], inferencia: Path, cache: Path) -> dict:
    total, por_sesion, por_archivo, faltantes, sin_referencia = der.Evaluador(), {}, {}, [], []
    for e in sorted(elementos, key=lambda e: e["id"]):
        if "diarizacion" not in e["modulos"]:
            continue
        if not e.get("referencia"):
            sin_referencia.append(e["id"])
            continue
        hipotesis = Path(inferencia) / e["id"] / "diarization.json"
        if not hipotesis.is_file():
            faltantes.append(f"{e['id']}/diarization.json")
            continue
        referencia = referencia_tarea(e, cache)
        segmentos = json.loads(hipotesis.read_text(encoding="utf-8"))["segments"]
        duracion = e["cuadros"] / FS
        por_archivo[e["id"]] = por_sesion.setdefault(e["sesion"], der.Evaluador()).evaluar(
            e["id"], referencia, segmentos, duracion)
        total.evaluar(e["id"], referencia, segmentos, duracion)
    return {"configuracion": der.DEFINICIONES, "herramienta": der.HERRAMIENTA,
            "referencia": "frases de los dos canales con la política de etiquetas de la Etapa 2 (construir de "
                          "evaluacion/diarizacion/referencia.py); hablantes figshare_v2_<sesión>_canal<n>",
            "politica_etiquetas_sha256": hashlib.sha256(POLITICA_JSON.read_bytes()).hexdigest(),
            "por_sesion": {s: ev.acumulado() for s, ev in sorted(por_sesion.items())},
            "total": total.acumulado() if por_archivo else None,
            "por_archivo": por_archivo, "faltantes": faltantes, "sin_referencia": sin_referencia}
