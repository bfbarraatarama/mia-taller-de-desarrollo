"""WER y CER de la transcripción, sin umbral (requisito «Métricas de transcripción», D10).

Normalización: minúsculas y cada signo de puntuación o símbolo reemplazado por un espacio, conservando las tildes.
Referencia de Figshare: las frases de los dos canales ordenadas por inicio, sin las etiquetas `<…>`, sin las palabras
cortadas (terminadas en «-») y sin lo que no tiene letras; cada exclusión se cuenta.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

import numpy as np

from .audio import leer_miembro

NORMALIZACION = ("minúsculas; puntuación y símbolos reemplazados por espacios; tildes conservadas. Figshare: sin "
                 "etiquetas <…>, sin palabras cortadas («palabra-») y sin tokens sin letras, contados en `excluidos`")
ETIQUETA = re.compile(r"<[^>]*>")
CAMPOS = ("sustituciones", "inserciones", "borrados", "palabras_referencia", "palabras_hipotesis",
          "errores_caracteres", "caracteres_referencia")


def normalizar(texto: str) -> list[str]:
    limpio = "".join(" " if unicodedata.category(c)[0] in "PS" else c for c in texto.lower())
    return limpio.split()


def _alinear(ref: list[str], hip: list[str]) -> tuple[int, int, int]:
    """(sustituciones, inserciones, borrados) de una alineación de distancia mínima."""
    n, m = len(ref), len(hip)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j - 1] + (ref[i - 1] != hip[j - 1]), d[i - 1][j] + 1, d[i][j - 1] + 1)
    s = ins = bor = 0
    i, j = n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hip[j - 1]):
            s += ref[i - 1] != hip[j - 1]
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            bor, i = bor + 1, i - 1
        else:
            ins, j = ins + 1, j - 1
    return s, ins, bor


def _distancia(a: str, b: str) -> int:
    """Levenshtein por caracteres, con filas vectorizadas (las referencias de Figshare tienen miles)."""
    if not a or not b:
        return len(a) or len(b)
    bb = np.frombuffer(b.encode("utf-32-le"), dtype=np.uint32)
    previa = np.arange(len(bb) + 1)
    indices = np.arange(len(bb) + 1)
    for caracter in np.frombuffer(a.encode("utf-32-le"), dtype=np.uint32):
        parcial = np.empty_like(previa)
        parcial[0] = previa[0] + 1
        parcial[1:] = np.minimum(previa[1:] + 1, previa[:-1] + (bb != caracter))
        previa = np.minimum.accumulate(parcial - indices) + indices  # inserciones a lo largo de la fila
    return int(previa[-1])


def _tasas(r: dict) -> dict:
    n, c = r["palabras_referencia"], r["caracteres_referencia"]
    r["wer"] = (r["sustituciones"] + r["inserciones"] + r["borrados"]) / n if n else None
    r["cer"] = r["errores_caracteres"] / c if c else None
    return r


def errores(ref: list[str], hip: list[str]) -> dict:
    s, ins, bor = _alinear(ref, hip)
    a, b = " ".join(ref), " ".join(hip)
    return _tasas({"sustituciones": s, "inserciones": ins, "borrados": bor, "palabras_referencia": len(ref),
                   "palabras_hipotesis": len(hip), "errores_caracteres": _distancia(a, b),
                   "caracteres_referencia": len(a)})


def referencia_figshare(*canales: str) -> tuple[list[str], dict[str, int]]:
    """Tokens de referencia de una tarea (frases de todos los canales por orden de inicio) y exclusiones."""
    frases = []
    for canal, texto in enumerate(canales, start=1):
        for linea in texto.splitlines():
            campos = linea.split("\t", 2)
            if len(campos) == 3 and campos[2].strip() != "#":
                frases.append((float(campos[0]), canal, campos[2].strip()))
    excluidos = {"etiquetas": 0, "fragmentos": 0, "sin_letras": 0}
    tokens = []
    for _, _, texto in sorted(frases):
        excluidos["etiquetas"] += len(ETIQUETA.findall(texto))
        for token in ETIQUETA.sub(" ", texto).split():
            if not any(c.isalpha() for c in token):
                excluidos["sin_letras"] += 1
            elif token.endswith("-"):
                excluidos["fragmentos"] += 1
            else:
                tokens += normalizar(token)
    return tokens, excluidos


def _hipotesis(asr: Path) -> list[str]:
    datos = json.loads(asr.read_text(encoding="utf-8"))
    return normalizar(" ".join(s["text"] for s in datos["segments"]))


def _sumar(destino: dict, r: dict) -> None:
    for campo in CAMPOS:
        destino[campo] = destino.get(campo, 0) + r[campo]


def metricas_stt(elementos: list[dict], inferencia: Path, cache: Path, *, verificar_hash: bool = True) -> dict:
    por_archivo, por_fuente, total, faltantes, sin_referencia = {}, {}, {}, [], []
    for e in sorted(elementos, key=lambda e: e["id"]):
        if "stt" not in e["modulos"]:
            continue
        if not e.get("referencia"):
            sin_referencia.append(e["id"])
            continue
        asr = Path(inferencia) / e["id"] / "asr.json"
        if not asr.is_file():
            faltantes.append(f"{e['id']}/asr.json")
            continue
        excluidos = None
        if e["fuente"] == "figshare":
            ref_info, canales = e["referencia"], []
            for entrada, esperado in sorted(ref_info["entradas"].items()):
                datos = leer_miembro(Path(cache) / ref_info["original"], entrada)
                if verificar_hash and hashlib.sha256(datos).hexdigest() != esperado:
                    raise ValueError(f"{entrada}: la referencia no coincide con el SHA-256 del manifiesto")
                canales.append(datos.decode("utf-8-sig"))
            ref, excluidos = referencia_figshare(*canales)
        else:
            ref = normalizar(e["referencia"])
        r = errores(ref, _hipotesis(asr))
        if excluidos is not None:
            r["excluidos"] = excluidos
        por_archivo[e["id"]] = r
        fuente = por_fuente.setdefault(e["fuente"], {"archivos": 0})
        fuente["archivos"] += 1
        _sumar(fuente, r)
        _sumar(total, r)
        if excluidos is not None:
            acumulado = fuente.setdefault("excluidos", {k: 0 for k in excluidos})
            for k, v in excluidos.items():
                acumulado[k] += v
    for r in [*por_fuente.values(), total]:
        if r:
            _tasas(r)
    return {"normalizacion": NORMALIZACION, "agregado": "suma de errores sobre suma de palabras (micro)",
            "por_fuente": por_fuente, "total": total, "por_archivo": por_archivo, "faltantes": faltantes, "sin_referencia": sin_referencia}
