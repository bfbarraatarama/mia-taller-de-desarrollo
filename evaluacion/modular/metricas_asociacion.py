"""Atribución de palabras de la asociación en Figshare, sin umbral (requisito «Atribución de palabras», D10).

Para cada palabra se toma el hablante de su intervención en la transcripción guardada por la Etapa 4 y el canal de la frase de referencia activo en su punto
medio. Las etiquetas de la diarización se traducen a canales con la misma correspondencia que la evaluación de la
diarización (`optimal_mapping` del DER estricto), no por su nombre. Las palabras se separan según cuántos canales
hablan en ese instante: uno (`sin_superposicion`), dos o más (`con_superposicion`, vale cualquiera de ellos) o
ninguno (`fuera_de_la_referencia`, no cuentan).
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

from pyannote.core import Segment, Timeline
from pyannote.metrics.diarization import DiarizationErrorRate

from evaluacion.diarizacion.der import anotacion
from src.asociacion.contrato import validar_asr
from src.asociacion.texto import alinear

from .audio import FS
from .metricas_diar import referencia_tarea


def palabras_asignadas(transcripcion: list[dict], asr: dict) -> tuple[list[tuple[float, float, str | None]], dict[str, int]]:
    """(inicio, fin, hablante) de cada palabra según la transcripción guardada, y lo que fue por respaldo.

    Se evalúa lo persistido, no se vuelve a ejecutar la asociación: cada intervención con `timing` «word» indica en
    `source` el segmento y el tramo de su texto, y `alinear()` sobre el ASR normalizado da el tramo de cada palabra;
    la palabra toma el hablante de su intervención. Las intervenciones por segmento («segment» o «unknown») no
    tienen tiempos por palabra y se cuentan aparte.
    """
    palabras, respaldo, alineadas = [], {"intervenciones": 0, "palabras": 0}, {}
    for i in transcripcion:
        if i.get("timing") != "word":
            respaldo["intervenciones"] += 1
            respaldo["palabras"] += len(i["text"].split())
            continue
        fuente = i["source"]
        if fuente["segment"] not in alineadas:
            alineadas[fuente["segment"]] = alinear(asr["segments"][fuente["segment"]]) or []
        for w in alineadas[fuente["segment"]]:
            if fuente["start"] <= w["char_start"] and w["char_end"] <= fuente["end"]:
                palabras.append((w["start"], w["end"], i["speaker"]))
    palabras.sort(key=lambda p: (p[0], p[1]))
    return palabras, respaldo


def _activos(referencia: list[dict], t: float) -> set[str]:
    return {s["speaker"] for s in referencia if s["start"] <= t < s["end"]}


def _superposicion(referencia: list[dict]) -> list[tuple[float, float]]:
    """Intervalos con dos o más hablantes de referencia activos."""
    eventos = sorted([(s["start"], 1) for s in referencia] + [(s["end"], -1) for s in referencia],
                     key=lambda e: (e[0], e[1]))
    tramos, activos, desde = [], 0, None
    for t, delta in eventos:
        antes, activos = activos, activos + delta
        if antes < 2 <= activos:
            desde = t
        elif antes >= 2 > activos and t > desde:
            tramos.append((desde, t))
    return tramos


def _grupo(palabras: int, correctas: int) -> dict:
    return {"palabras": palabras, "correctas": correctas,
            "porcentaje": round(100 * correctas / palabras, 1) if palabras else None}


def atribucion(palabras: list[tuple], referencia: list[dict], diarizacion: list[dict], duracion: float,
               intervenciones: list[dict]) -> dict:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="'uem' was approximated")
        correspondencia = DiarizationErrorRate(collar=0.0, skip_overlap=False).optimal_mapping(
            anotacion(referencia), anotacion(diarizacion), uem=Timeline([Segment(0.0, float(duracion))]))
    cuentas = {"sin_superposicion": [0, 0], "con_superposicion": [0, 0]}
    fuera = sin_hablante = 0
    for ini, fin, hablante in palabras:
        activos = _activos(referencia, (ini + fin) / 2)
        if not activos:
            fuera += 1
            continue
        grupo = cuentas["con_superposicion" if len(activos) >= 2 else "sin_superposicion"]
        grupo[0] += 1
        grupo[1] += correspondencia.get(hablante) in activos
        sin_hablante += hablante is None
    real = _superposicion(referencia)
    sin_tiempo = sum(i.get("start") is None for i in intervenciones)  # timing «unknown» (#19): no se ubican
    intervenciones = [i for i in intervenciones if i.get("start") is not None]
    toca = [any(min(i["end"], b) > max(i["start"], a) for a, b in real) for i in intervenciones]
    marcas = {"total": len(intervenciones), "sin_tiempo": sin_tiempo, "sobre_superposicion_real": sum(toca)}
    for marca in ("ambiguous", "overlap"):
        marcas[marca] = sum(bool(i.get(marca)) for i in intervenciones)
        marcas[f"{marca}_sobre_superposicion_real"] = sum(bool(i.get(marca)) and t for i, t in zip(intervenciones, toca))
    return {"correspondencia": dict(sorted(correspondencia.items())),
            **{k: _grupo(*v) for k, v in cuentas.items()},
            "fuera_de_la_referencia": fuera, "sin_hablante": sin_hablante, "intervenciones": marcas}


def _acumular(destino: dict, r: dict) -> None:
    for g in ("sin_superposicion", "con_superposicion"):
        d = destino.setdefault(g, {"palabras": 0, "correctas": 0})
        d["palabras"] += r[g]["palabras"]
        d["correctas"] += r[g]["correctas"]
    for k in ("fuera_de_la_referencia", "sin_hablante"):
        destino[k] = destino.get(k, 0) + r[k]
    if "respaldo" in r:
        acumulado = destino.setdefault("respaldo", {"intervenciones": 0, "palabras": 0})
        for k, v in r["respaldo"].items():
            acumulado[k] += v
    marcas = destino.setdefault("intervenciones", {})
    for k, v in r["intervenciones"].items():
        marcas[k] = marcas.get(k, 0) + v


def _cerrar(destino: dict) -> dict:
    total = [0, 0]
    for g in ("sin_superposicion", "con_superposicion"):
        p, c = destino[g]["palabras"], destino[g]["correctas"]
        destino[g] = _grupo(p, c)
        total = [total[0] + p, total[1] + c]
    destino["todas"] = _grupo(*total)
    return destino


def metricas_asociacion(elementos: list[dict], inferencia: Path, cache: Path, datos: Path) -> dict:
    por_archivo, por_sesion, total, faltantes, sin_referencia = {}, {}, {}, [], []
    for e in sorted(elementos, key=lambda e: e["id"]):
        if "asociacion" not in e["modulos"]:
            continue
        if not e.get("referencia"):
            sin_referencia.append(e["id"])
            continue
        carpeta = Path(inferencia) / e["id"]
        necesarios = ("diarization.json", "asr.json", "transcription.json")
        if not all((carpeta / n).is_file() for n in necesarios):
            faltantes.append(e["id"])
            continue
        duracion = e["cuadros"] / FS
        diar = json.loads((carpeta / "diarization.json").read_text(encoding="utf-8"))["segments"]
        trans = json.loads((carpeta / "transcription.json").read_text(encoding="utf-8"))["segments"]
        asr, _ = validar_asr(json.loads((carpeta / "asr.json").read_text(encoding="utf-8")), duracion)
        palabras, respaldo = palabras_asignadas(trans, asr)
        r = atribucion(palabras, referencia_tarea(e, cache), diar, duracion, trans)
        r["respaldo"] = respaldo
        por_archivo[e["id"]] = r
        _acumular(por_sesion.setdefault(e["sesion"], {}), r)
        _acumular(total, r)
    return {"criterio": "hablante de cada palabra (Etapa 4) contra el canal de referencia activo en su punto medio, "
                        "con la correspondencia de etiquetas del DER estricto",
            "por_sesion": {s: _cerrar(v) for s, v in sorted(por_sesion.items())},
            "total": _cerrar(total) if total else None, "por_archivo": por_archivo,
            "faltantes": faltantes, "sin_referencia": sin_referencia}
