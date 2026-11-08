"""Normalización de los segmentos que devuelve el modelo (design.md §4).

Regla: **recortar y no descartar**. Todo segmento con alguna parte dentro del audio se recorta a `[0, D3]`
(con `D3 <= D`, la duración real truncada a 3 decimales), sea cual sea su exceso. Solo se descartan los que
no tienen ninguna parte dentro del audio o quedan vacíos tras redondear. Así ningún tiempo escrito queda
fuera del WAV y no se pierde habla real por un exceso de la resolución del modelo.
`acotar` y `techo_3_decimales` también los usa `evaluacion/referencia.py` para el RTTM.
"""

from __future__ import annotations

import math
from typing import Iterable

# Campo heredado: se sigue registrando en el meta como `tolerancia_fin_s` por compatibilidad, pero ya no
# controla descartes ni correcciones (regla anterior, reemplazada el 08/11/2026; ver design.md §4).
TOLERANCIA_FIN_S = 0.05


def techo_3_decimales(duracion: float) -> float:
    """Mayor valor con 3 decimales que no supera `duracion`."""
    d3 = math.floor(duracion * 1000) / 1000
    if d3 > duracion:  # por la representación binaria
        d3 = (math.floor(duracion * 1000) - 1) / 1000
    return max(d3, 0.0)


def acotar(inicio: float, fin: float, d3: float) -> tuple[float, float] | None:
    """Redondea a 3 decimales dentro de `[0, d3]`; devuelve None si el intervalo queda vacío."""
    s = min(max(round(inicio, 3), 0.0), d3) + 0.0  # + 0.0 convierte -0.0 en 0.0
    e = min(max(round(fin, 3), 0.0), d3) + 0.0
    if s >= e:
        return None
    return s, e


def normalizar(turnos: Iterable[tuple[float, float, str]], duracion: float):
    """Devuelve (segmentos, corregidos, descartados, exceso_fin_max_s).

    `turnos` son tuplas (start, end, speaker) con tiempos crudos. Los segmentos salen ordenados por
    (start, end, speaker); los solapamientos entre hablantes se conservan. `exceso_fin_max_s` es el mayor
    `end - duracion` entre los segmentos recortados por el final que se escriben (0.0 si no hubo ninguno).
    """
    d3 = techo_3_decimales(duracion)
    segmentos, corregidos, descartados, exceso_max = [], 0, 0, 0.0
    for inicio, fin, hablante in turnos:
        inicio, fin = float(inicio), float(fin)
        if not (math.isfinite(inicio) and math.isfinite(fin)):
            descartados += 1
            continue
        # 1. Decisión con tiempos crudos contra D, sin tolerancia: solo se descarta lo que está fuera del audio.
        if inicio >= duracion or fin <= 0:
            descartados += 1
            continue
        corregido = fin > duracion or inicio < 0
        # 2 a 4. Techo, redondeo acotado y descarte de intervalos vacíos.
        acotado = acotar(inicio, fin, d3)
        if acotado is None:
            descartados += 1
            continue
        if corregido:
            corregidos += 1
            if fin > duracion:
                exceso_max = max(exceso_max, fin - duracion)
        segmentos.append({"start": acotado[0], "end": acotado[1], "speaker": str(hablante)})
    segmentos.sort(key=lambda s: (s["start"], s["end"], s["speaker"]))
    return segmentos, corregidos, descartados, round(exceso_max, 4)
