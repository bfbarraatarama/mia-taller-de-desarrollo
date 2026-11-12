"""Referencia de evaluación de S26 (design.md §11, tareas 6.5 y 6.6).

- Tarea 6.5: clasificación de las líneas (`#` excluido, texto con letras = habla, etiquetas sin letras según
  `politica_etiquetas.json`), unión de intervalos del mismo canal, solapamiento entre canales conservado, ajuste de
  los fines que exceden la duración real en 0,01 s o menos, y RTTM con tiempos acotados por `segmentos.acotar`.
- Tarea 6.6: validación de la referencia antes de las métricas y el indicador de cobertura por canal.

Las anotaciones originales no se modifican: todo se calcula en memoria a partir de las filas leídas.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from segmentos import acotar, techo_3_decimales  # noqa: E402

POLITICA_JSON = Path(__file__).resolve().parent / "politica_etiquetas.json"
CLASES = ("habla", "excluir")
SILENCIO = "#"
TOLERANCIA_FIN_S = 0.01  # valor por defecto; preparar_figshare pasa la importada del Hito 2 (la misma)

# Parámetros del indicador de cobertura (design.md §11). Van al manifiesto.
COBERTURA = {"ventana_s": 0.03, "paso_s": 0.01, "percentil_piso": 20, "margen_db": 12.0, "tramo_minimo_s": 0.3,
             "energia": "suma de cuadrados int64 por ventana; ventana asignada por su centro",
             "excluye_habla_del_otro_canal": True}


class ErrorReferencia(Exception):
    """La referencia no puede construirse (por ejemplo, etiquetas sin clasificar)."""


def hablante(sesion: str, canal: int) -> str:
    return f"figshare_v2_{sesion}_canal{canal}"


# --- política de etiquetas ------------------------------------------------------------------------------------

def leer_politica(ruta: Path = POLITICA_JSON) -> dict[str, str]:
    """{etiqueta: 'habla' | 'excluir'} de `politica_etiquetas.json`; ErrorReferencia si está mal formada."""
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ErrorReferencia(f"no se pudo leer la política de etiquetas {ruta}: {e}") from None
    etiquetas = datos.get("etiquetas") if isinstance(datos, dict) else None
    if not isinstance(etiquetas, dict):
        raise ErrorReferencia(f"{Path(ruta).name}: falta el objeto 'etiquetas'")
    for etiqueta, clase in etiquetas.items():
        if clase not in CLASES:
            raise ErrorReferencia(f"{Path(ruta).name}: la etiqueta {etiqueta!r} tiene la clase {clase!r} "
                                  f"(se espera {' o '.join(CLASES)})")
        if tiene_letras(etiqueta) or etiqueta == SILENCIO:
            raise ErrorReferencia(f"{Path(ruta).name}: {etiqueta!r} no es una etiqueta sin letras clasificable")
    return dict(etiquetas)


def tiene_letras(texto: str) -> bool:
    return any(c.isalpha() for c in texto)


def clasificar(texto: str, politica: dict[str, str]) -> str:
    """'silencio', 'habla', 'excluir' o 'sin_clasificar'."""
    if texto == SILENCIO:
        return "silencio"
    if tiene_letras(texto):
        return "habla"
    return politica.get(texto, "sin_clasificar")


def inventario_etiquetas(anotaciones: dict[int, list], politica: dict[str, str]) -> dict[str, dict]:
    """{etiqueta sin letras distinta de '#': {apariciones, clase}} de las filas (linea, inicio, fin, texto)."""
    cuenta = Counter(f[3] for filas in anotaciones.values() for f in filas
                     if f[3] != SILENCIO and not tiene_letras(f[3]))
    return {e: {"apariciones": n, "clase": politica.get(e, "sin_clasificar")} for e, n in sorted(cuenta.items())}


# --- construcción ----------------------------------------------------------------------------------------------

def construir(anotaciones: dict[int, list], cuadros: int, fs: int, politica: dict[str, str], sesion: str = "S26",
              tolerancia_fin_s: float = TOLERANCIA_FIN_S) -> dict:
    """Referencia de una grabación a partir de las filas de cada canal ({1: [...], 2: [...]}).

    Devuelve {"segmentos": [{start, end, speaker}] ordenados por (start, speaker), "conteos", "ajustes_fin"}.
    Falla (ErrorReferencia) si hay etiquetas sin clasificar o un fin fuera de la tolerancia.
    """
    sin_clasificar = {e: v["apariciones"] for e, v in inventario_etiquetas(anotaciones, politica).items()
                      if v["clase"] == "sin_clasificar"}
    if sin_clasificar:
        raise ErrorReferencia("etiquetas sin clasificar en politica_etiquetas.json: "
                              + ", ".join(f"{e!r} ({n})" for e, n in sin_clasificar.items()))
    duracion = cuadros / fs
    d3 = techo_3_decimales(duracion)
    segmentos, conteos, ajustes = [], {}, []
    for canal in sorted(anotaciones):
        habla, excluidas = [], Counter()
        silencios = 0
        for linea, inicio, fin, texto, *resto in anotaciones[canal]:
            clase = clasificar(texto, politica)
            if clase == "silencio":
                silencios += 1
                continue
            if clase == "excluir":
                excluidas[texto] += 1
                continue
            if fin > duracion:
                exceso = fin - duracion
                if exceso > tolerancia_fin_s + 1e-12:
                    raise ErrorReferencia(f"channel{canal}:{linea}: fin {fin} excede la duración en {exceso:.4f} s")
                ajustes.append({"canal": canal, "linea": linea, "fin_original_s": fin,
                                "fin_original_texto": resto[0] if resto else repr(fin),
                                "fin_ajustado_s": duracion, "fin_ajustado_cuadros": cuadros})
                fin = duracion
            habla.append((inicio, fin))
        unidos, uniones = unir(habla)
        escritos = 0
        for inicio, fin in unidos:
            acotado = acotar(inicio, fin, d3)
            if acotado is not None:
                segmentos.append({"start": acotado[0], "end": acotado[1], "speaker": hablante(sesion, canal)})
                escritos += 1
        conteos[f"channel{canal}"] = {
            "intervalos": len(anotaciones[canal]), "habla": len(habla), "excluidos_por_almohadilla": silencios,
            "excluidos_por_etiqueta": dict(sorted(excluidas.items())), "uniones": uniones,
            "segmentos_referencia": escritos}
    segmentos.sort(key=lambda s: (s["start"], s["speaker"], s["end"]))
    return {"segmentos": segmentos, "conteos": conteos, "ajustes_fin": ajustes}


def unir(intervalos: list[tuple[float, float]]) -> tuple[list[tuple[float, float]], int]:
    """Une los intervalos superpuestos o contiguos de un mismo canal; devuelve (unidos, cantidad de uniones)."""
    unidos, uniones = [], 0
    for inicio, fin in sorted(intervalos):
        if unidos and inicio <= unidos[-1][1]:
            unidos[-1] = (unidos[-1][0], max(unidos[-1][1], fin))
            uniones += 1
        else:
            unidos.append((inicio, fin))
    return unidos, uniones


def rttm(segmentos: list[dict], uri: str) -> str:
    """Texto RTTM (tiempos a 3 decimales, fin de línea \\n) de segmentos ya acotados y ordenados."""
    lineas = [f"SPEAKER {uri} 1 {s['start']:.3f} {round(s['end'] - s['start'], 3):.3f} <NA> <NA> {s['speaker']} "
              f"<NA> <NA>" for s in segmentos]
    return "".join(linea + "\n" for linea in lineas)


def leer_rttm(texto: str) -> list[dict]:
    segmentos = []
    for numero, linea in enumerate(texto.splitlines(), 1):
        campos = linea.split()
        if not campos:
            continue
        if len(campos) < 8 or campos[0] != "SPEAKER":
            raise ErrorReferencia(f"RTTM línea {numero}: mal formada")
        inicio, dur = float(campos[3]), float(campos[4])
        segmentos.append({"start": round(inicio, 3), "end": round(inicio + dur, 3), "speaker": campos[7]})
    return segmentos


# --- tarea 6.6: validación antes de las métricas ----------------------------------------------------------------

def validar_referencia(segmentos: list[dict], duracion: float) -> dict:
    """{utilizable, motivo}: `0 <= start < end <= duración`, hablante, sin duplicados y al menos un segmento."""
    if not segmentos:
        return {"utilizable": False, "motivo": "referencia sin habla"}
    vistos = set()
    for i, s in enumerate(segmentos, 1):
        inicio, fin, quien = s.get("start"), s.get("end"), s.get("speaker")
        if not isinstance(quien, str) or not quien.strip():
            return {"utilizable": False, "motivo": f"segmento {i}: hablante vacío"}
        if not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (inicio, fin)):
            return {"utilizable": False, "motivo": f"segmento {i}: tiempos no numéricos"}
        if not 0 <= inicio < fin <= duracion + 1e-9:
            return {"utilizable": False,
                    "motivo": f"segmento {i}: [{inicio}, {fin}] fuera de 0 <= start < end <= {duracion}"}
        clave = (inicio, fin, quien)
        if clave in vistos:
            return {"utilizable": False, "motivo": f"segmento {i}: duplicado"}
        vistos.add(clave)
    return {"utilizable": True, "motivo": None}


def metricas_nulas(motivo: str) -> dict:
    """Métricas de una grabación con referencia no utilizable: todas en null, con el motivo, sin ningún valor."""
    return {"der_estricto": None, "der_tolerancia": None, "jer": None, "componentes": None, "motivo": motivo}


# --- tarea 6.6: indicador de cobertura ---------------------------------------------------------------------------

def _mascara(centros: np.ndarray, intervalos: list[tuple[float, float]]) -> np.ndarray:
    m = np.zeros(centros.shape, dtype=bool)
    for inicio, fin in intervalos:
        m |= (centros >= inicio) & (centros < fin)
    return m


def _tramos(mascara: np.ndarray, centros: np.ndarray, paso: float, minimo: float) -> list[tuple[float, float]]:
    tramos, i, n = [], 0, len(mascara)
    while i < n:
        if not mascara[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and mascara[j + 1]:
            j += 1
        if (j - i + 1) * paso >= minimo - 1e-9:
            tramos.append((round(float(centros[i]) - paso / 2, 3), round(float(centros[j]) + paso / 2, 3)))
        i = j + 1
    return tramos


def _dbfs(energia: int, ventana: int) -> float:
    """Potencia media de la ventana en dB respecto del fondo de escala de PCM16 (solo para leer)."""
    return 10 * math.log10(max(energia, 1) / ventana / 32768 ** 2)


def cobertura(estereo: np.ndarray, fs: int, anotaciones: dict[int, list], politica: dict[str, str]) -> dict:
    """Indicador por canal (solo indicio; no cambia la referencia). `estereo` es int16 de forma (cuadros, 2)."""
    ventana, paso = round(COBERTURA["ventana_s"] * fs), round(COBERTURA["paso_s"] * fs)
    n = estereo.shape[0]
    inicios = np.arange(0, max(n - ventana, 0) + 1, paso)
    centros = (inicios + ventana / 2) / fs
    habla = {c: [(f[1], f[2]) for f in filas if clasificar(f[3], politica) == "habla"]
             for c, filas in anotaciones.items()}
    silencio = {c: [(f[1], f[2]) for f in filas if f[3] == SILENCIO] for c, filas in anotaciones.items()}
    resultado = {}
    for c in sorted(anotaciones):
        x = estereo[:, c - 1].astype(np.int64)
        acumulado = np.concatenate([[0], np.cumsum(x * x)])
        energia = acumulado[inicios + ventana] - acumulado[inicios]      # enteros exactos
        en_silencio = _mascara(centros, silencio[c])
        en_habla = _mascara(centros, habla[c])
        otro = [o for o in anotaciones if o != c]
        en_habla_otro = _mascara(centros, [i for o in otro for i in habla[o]])
        if not en_silencio.any():
            resultado[f"channel{c}"] = {"calculable": False, "motivo": "el canal no tiene intervalos '#'"}
            continue
        piso = int(np.percentile(energia[en_silencio], COBERTURA["percentil_piso"], method="lower"))
        umbral = max(piso, 1) * 10 ** (COBERTURA["margen_db"] / 10)
        alta = energia > umbral
        sin_anotar = alta & en_silencio & ~en_habla & ~en_habla_otro
        tramos = _tramos(sin_anotar, centros, COBERTURA["paso_s"], COBERTURA["tramo_minimo_s"])
        ventanas_habla = int(en_habla.sum())
        baja = int((en_habla & ~alta).sum())
        resultado[f"channel{c}"] = {
            "calculable": True,
            "piso_dbfs": round(_dbfs(piso, ventana), 2),
            "umbral_dbfs": round(_dbfs(piso, ventana) + COBERTURA["margen_db"], 2),
            "posible_habla_sin_anotar_s": round(sum(f - i for i, f in tramos), 3),
            "posible_habla_sin_anotar_tramos": [[i, f] for i, f in tramos],
            "habla_anotada_ventanas": ventanas_habla,
            "habla_anotada_energia_baja_ventanas": baja,
            "habla_anotada_energia_baja_proporcion": round(baja / ventanas_habla, 4) if ventanas_habla else None,
            "indicio": "solo indicio a revisar; no cambia la referencia",
        }
    return resultado
