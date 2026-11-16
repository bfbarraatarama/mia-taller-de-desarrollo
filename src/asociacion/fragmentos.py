"""Fragmento de audio por hablante para las fichas del etiquetado (D6 de design.md). Sin Qt ni audio.

Para cada etiqueta, una secuencia de fragmentos que «Otro fragmento» recorre en orden y vuelve a empezar:
- candidatos: tramos solos de duración >= máx(media de sus tramos solos, 5 s), en una permutación con semilla;
- si no hay candidatos (respaldo 1): el tramo solo más largo;
- si nunca habla sola (respaldo 2): el turno más largo, marcado como superpuesto para avisar en la ficha.
Un fragmento de más de 15 s se recorta a sus 15 s centrales. Su texto se toma literalmente de asr.json: palabras cuyo punto medio cae en [start, end),
o segmentos de resolución incompleta incluidos por completo.

Tiempos en milisegundos enteros; la media se compara como producto de enteros.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .asociacion import Asociacion, Turnos
from .texto import alinear, intervalo_segmento

MINIMO_MS = 5_000
MAXIMO_MS = 15_000


@dataclass(frozen=True)
class Fragmento:
    start: float
    end: float
    texto: str
    superpuesto: bool  # True solo en el respaldo 2: la ficha avisa que se oye otra voz
    texto_incierto: bool = False


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


def _texto_fragmento(asr: dict, ini: int, fin: int) -> tuple[str, bool]:
    """Usa fragmentos literales; no mutila segmentos sin correspondencia completa."""
    elegidas = []
    incierto = False
    for seg in asr.get("segments", []):
        palabras = alinear(seg)
        if not palabras:
            intervalo = intervalo_segmento(seg)
            if intervalo is not None:
                a, b = (round(t * 1000) for t in intervalo)
                if a < fin and b > ini:
                    incierto = True
                    if ini <= a and b <= fin:
                        elegidas.append(seg["text"].strip())
            elif any(round(w["start"] * 1000) < fin and round(w["end"] * 1000) > ini for w in seg["words"]):
                incierto = True
            continue
        grupo = []
        for w in palabras:
            medio2 = round(w["start"] * 1000) + round(w["end"] * 1000)
            if 2 * ini <= medio2 < 2 * fin:
                grupo.append(w)
            elif grupo:
                elegidas.append(seg["text"][grupo[0]["char_start"]:grupo[-1]["char_end"]])
                grupo = []
        if grupo:
            elegidas.append(seg["text"][grupo[0]["char_start"]:grupo[-1]["char_end"]])
    return " ".join(elegidas), incierto


def texto(asr: dict, ini: int, fin: int) -> str:
    return _texto_fragmento(asr, ini, fin)[0]


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
            contenido, incierto = _texto_fragmento(asociacion.asr, ini, fin)
            secuencia.append(Fragmento(start=ini / 1000, end=fin / 1000, texto=contenido,
                                       superpuesto=superpuesto, texto_incierto=incierto))
        resultado[e] = Fragmentos(etiqueta=e, secuencia=tuple(secuencia), origen=origen)
    return resultado
