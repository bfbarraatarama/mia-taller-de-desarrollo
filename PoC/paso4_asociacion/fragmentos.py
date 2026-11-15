"""Fragmento de audio por hablante para las fichas del etiquetado (D6 de design.md). Sin Qt ni audio.

Para cada etiqueta, una secuencia de fragmentos que «Otro fragmento» recorre en orden y vuelve a empezar:
- candidatos: tramos solos de duración >= máx(media de sus tramos solos, 5 s), en una permutación con semilla;
- si no hay candidatos (respaldo 1): el tramo solo más largo;
- si nunca habla sola (respaldo 2): el turno más largo, marcado como superpuesto para avisar en la ficha.
Un fragmento de más de 15 s se recorta a sus 15 s centrales. Su texto son las palabras de asr.json cuyo punto
medio cae en [start, end).

Tiempos en milisegundos enteros; la media se compara como producto de enteros.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from asociacion import Asociacion, Turnos

MINIMO_MS = 5_000
MAXIMO_MS = 15_000


@dataclass(frozen=True)
class Fragmento:
    start: float
    end: float
    texto: str
    superpuesto: bool  # True solo en el respaldo 2: la ficha avisa que se oye otra voz


@dataclass(frozen=True)
class Fragmentos:
    etiqueta: str
    secuencia: tuple[Fragmento, ...]
    origen: str  # "candidatos", "tramo_solo_mas_largo" o "turno_mas_largo"

    def en(self, i: int) -> Fragmento:
        """Fragmento i (desde 0) de la secuencia, que vuelve a empezar al agotarse."""
        return self.secuencia[i % len(self.secuencia)]


def tramos_solos(turnos: Turnos) -> dict[str, list[tuple[int, int]]]:
    """Intervalos máximos en que cada etiqueta es la única activa. Mismo criterio que evaluacion/tramos_solos.py."""
    eventos = sorted((t, delta, e) for e in turnos.etiquetas for ini, fin in turnos.intervalos(e)
                     for t, delta in ((ini, 1), (fin, -1)))
    solos: dict[str, list[list[int]]] = {e: [] for e in turnos.etiquetas}
    activas: set[str] = set()
    previo = None
    for t, delta, e in eventos:  # en el mismo instante, los fines (−1) van antes que los inicios
        if previo is not None and t > previo and len(activas) == 1:
            (unica,) = activas
            tramos = solos[unica]
            if tramos and tramos[-1][1] == previo:
                tramos[-1][1] = t
            else:
                tramos.append([previo, t])
        if delta > 0:
            activas.add(e)
        else:
            activas.discard(e)
        previo = t
    return {e: [(i, f) for i, f in v] for e, v in solos.items()}


def semilla(sha256_diarizacion: str) -> int:
    """Primeros 8 bytes del SHA-256 de diarization.json."""
    return int(sha256_diarizacion[:16], 16)


def recortar(ini: int, fin: int) -> tuple[int, int]:
    """Los 15 s centrales si el intervalo dura más."""
    sobra = (fin - ini) - MAXIMO_MS
    if sobra <= 0:
        return ini, fin
    return ini + sobra // 2, ini + sobra // 2 + MAXIMO_MS


def _secuencia(etiqueta: str, solos: list[tuple[int, int]], turnos: list[tuple[int, int]],
               semilla_: int) -> tuple[list[tuple[int, int]], str, bool]:
    """(intervalos en orden de presentación, origen, superpuesto)."""
    if solos:
        total = sum(f - i for i, f in solos)
        candidatos = [(i, f) for i, f in solos if (f - i) >= MINIMO_MS and (f - i) * len(solos) >= total]
        if candidatos:
            # str como semilla: determinista entre procesos, a diferencia de hash()
            random.Random(f"{semilla_}/{etiqueta}").shuffle(candidatos)
            return candidatos, "candidatos", False
        return [max(solos, key=lambda t: (t[1] - t[0], -t[0]))], "tramo_solo_mas_largo", False
    return [max(turnos, key=lambda t: (t[1] - t[0], -t[0]))], "turno_mas_largo", True


def texto(asr: dict, ini: int, fin: int) -> str:
    """Palabras cuyo punto medio cae en [ini, fin). Un segmento sin palabras cuenta como una sola."""
    elegidas = []
    for seg in asr.get("segments", []):
        for w in seg["words"] or [{"word": seg["text"], "start": seg["start"], "end": seg["end"]}]:
            medio2 = round(w["start"] * 1000) + round(w["end"] * 1000)  # punto medio × 2, en ms enteros
            if 2 * ini <= medio2 < 2 * fin:
                elegidas.append(w["word"].strip())
    return " ".join(elegidas)


def fragmentos(asociacion: Asociacion) -> dict[str, Fragmentos]:
    """Secuencia de fragmentos de cada etiqueta de diarization.json (vacío si no hay etiquetas)."""
    turnos = Turnos(asociacion.turnos)
    solos = tramos_solos(turnos)
    s = semilla(asociacion.sha256["diarization.json"])
    resultado = {}
    for e in turnos.etiquetas:
        intervalos, origen, superpuesto = _secuencia(e, solos[e], turnos.intervalos(e), s)
        secuencia = []
        for ini, fin in intervalos:
            ini, fin = recortar(ini, fin)
            secuencia.append(Fragmento(start=ini / 1000, end=fin / 1000, texto=texto(asociacion.asr, ini, fin),
                                       superpuesto=superpuesto))
        resultado[e] = Fragmentos(etiqueta=e, secuencia=tuple(secuencia), origen=origen)
    return resultado
