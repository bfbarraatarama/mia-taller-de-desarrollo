"""Paso 1 de la API de la Etapa 4 (D7): valida las entradas y asocia palabras con hablantes. No escribe nada.

Reglas de `design.md`, con las precisiones de `docs/temporalidad-transcripcion.md`:
- D1: cada palabra va al hablante con más milisegundos de turno dentro de ella.
- D2: empate de cobertura: el hablante de la palabra anterior (en todo asr.json) si está entre los empatados; si no,
  el del turno más largo; si persiste, la etiqueta menor.
- D3: palabra sin turno: el turno más cercano si está a 0,25 s o menos (empate de distancia: misma regla que D2);
  si no, `speaker: null`.
- D4: intervenciones cortadas por cambio de hablante y en cada segmento de Whisper.
- D5: `overlap` si hay 0,2 s o más con dos o más hablantes; `ambiguous` si no hay hablante, si otra etiqueta cubre
  el 30 % o más, o si la propia cubre menos del 50 %. Se propaga también la incertidumbre de cada palabra.

Los tiempos se comparan en milisegundos enteros, y los porcentajes como productos de enteros, para que los valores
límite no dependan del redondeo en coma flotante. Un «turno» es la unión de los turnos que se tocan de una etiqueta.
"""

from __future__ import annotations

import bisect
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .contrato import CAMPOS_INTERVENCION, validar_asr, validar_audio, validar_diarizacion
from .errores import AsociacionError
from .texto import alinear, intervalo_segmento

NOMBRES_ENTRADA = {"audio": "audio.wav", "diarizacion": "diarization.json", "asr": "asr.json"}

HUECO_MAX_MS = 250          # D3
OVERLAP_MIN_MS = 200        # D5
SEGUNDO_HABLANTE_PCT = 30   # D5: otra etiqueta con este porcentaje o más → ambiguous
PROPIO_PCT = 50             # D5: la propia etiqueta con menos de este porcentaje → ambiguous
UMBRALES = {"hueco_max_s": HUECO_MAX_MS / 1000, "overlap_min_s": OVERLAP_MIN_MS / 1000,
            "segundo_hablante_min": SEGUNDO_HABLANTE_PCT / 100, "propio_min": PROPIO_PCT / 100}


@dataclass
class Intervencion:
    start: float | None
    end: float | None
    speaker: str | None
    name: str | None
    text: str
    overlap: bool | None
    ambiguous: bool
    timing: str = "word"
    speakers_detected: list[dict] | None = None
    source: dict = field(default_factory=dict)

    def a_dict(self) -> dict:
        d = asdict(self)
        return {c: d[c] for c in CAMPOS_INTERVENCION}


@dataclass
class Rutas:
    audio: Path
    diarizacion: Path
    asr: Path
    salida: Path


@dataclass
class Asociacion:
    rutas: Rutas
    duracion: float
    etiquetas: tuple[str, ...]
    turnos: list[dict]
    intervenciones: list[Intervencion]
    sha256: dict[str, str]
    recortes_asr: dict[str, int]
    conteos: dict[str, int] = field(default_factory=dict)
    asr: dict = field(default_factory=dict)  # asr.json validado, redondeado y recortado (texto de los fragmentos)


def resolver_rutas(carpeta=None, *, audio=None, diarizacion=None, asr=None, salida=None) -> Rutas:
    """Carpeta de la reunión por defecto; las rutas explícitas la reemplazan (D7)."""
    carpeta = Path(carpeta) if carpeta is not None else None
    explicitas = {"audio": audio, "diarizacion": diarizacion, "asr": asr}
    rutas = {}
    for clave, valor in explicitas.items():
        if valor is not None:
            rutas[clave] = Path(valor)
        elif carpeta is not None:
            rutas[clave] = carpeta / NOMBRES_ENTRADA[clave]
        else:
            raise AsociacionError("parametros", f"falta la ruta de {clave}: indicá la carpeta de la reunión "
                                                f"o --{clave}")
    if salida is None and carpeta is None:
        raise AsociacionError("parametros", "falta la carpeta de salida: indicá la carpeta de la reunión o --salida")
    return Rutas(**rutas, salida=Path(salida) if salida is not None else carpeta)


def _sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _leer_json(ruta: Path, paso: str) -> tuple[object, str]:
    try:
        contenido = ruta.read_bytes()
        return json.loads(contenido), hashlib.sha256(contenido).hexdigest()
    except OSError as e:
        raise AsociacionError(paso, f"{ruta}: no se pudo leer ({e.strerror or e})", archivo=ruta) from e
    except ValueError as e:
        raise AsociacionError(paso, f"{ruta}: no es JSON válido ({e})", archivo=ruta) from e


def ms(segundos: float) -> int:
    return round(segundos * 1000)


class Turnos:
    """Turnos de diarization.json por etiqueta, unidos si se tocan, para medir cobertura con bisect."""

    def __init__(self, segmentos: list[dict]):
        por_etiqueta: dict[str, list[list[int]]] = {}
        for s in sorted(segmentos, key=lambda s: (s["start"], s["end"])):
            intervalos = por_etiqueta.setdefault(s["speaker"], [])
            ini, fin = ms(s["start"]), ms(s["end"])
            if intervalos and ini <= intervalos[-1][1]:
                intervalos[-1][1] = max(intervalos[-1][1], fin)
            else:
                intervalos.append([ini, fin])
        self.etiquetas = tuple(sorted(por_etiqueta))
        self._inicios = {e: [i for i, _ in v] for e, v in por_etiqueta.items()}
        self._fines = {e: [f for _, f in v] for e, v in por_etiqueta.items()}

    def intervalos(self, etiqueta: str) -> list[tuple[int, int]]:
        """Turnos unidos de `etiqueta`, en milisegundos y ordenados."""
        return list(zip(self._inicios[etiqueta], self._fines[etiqueta]))

    def cobertura(self, etiqueta: str, ini: int, fin: int) -> int:
        """Milisegundos de [ini, fin) cubiertos por los turnos de `etiqueta`."""
        inicios, fines = self._inicios[etiqueta], self._fines[etiqueta]
        total = 0
        for k in range(bisect.bisect_right(fines, ini), len(inicios)):
            if inicios[k] >= fin:
                break
            total += min(fines[k], fin) - max(inicios[k], ini)
        return total

    def _cercano(self, etiqueta: str, ini: int, fin: int) -> tuple[int, int]:
        """(distancia, −largo) del turno de `etiqueta` más cercano a [ini, fin); entre los que se superponen
        (distancia 0), el más largo."""
        inicios, fines = self._inicios[etiqueta], self._fines[etiqueta]
        mejor = None
        for k in range(max(bisect.bisect_right(fines, ini) - 1, 0), len(inicios)):
            candidato = (max(0, inicios[k] - fin, ini - fines[k]), inicios[k] - fines[k])
            mejor = candidato if mejor is None else min(mejor, candidato)
            if inicios[k] >= fin:
                break
        return mejor

    def _desempatar(self, candidatos: list[str], ini: int, fin: int, anterior: str | None) -> str:
        """D2: continuidad con la palabra anterior; si no, el turno más largo; si no, la etiqueta menor."""
        if len(candidatos) == 1:
            return candidatos[0]
        if anterior in candidatos:
            return anterior
        return min(candidatos, key=lambda e: (self._cercano(e, ini, fin)[1], e))

    def asignar(self, ini: int, fin: int, anterior: str | None = None) -> tuple[str | None, str]:
        """Devuelve (etiqueta o None, regla que decidió: "D1", "D2", "D3" o "sin_turno")."""
        coberturas = {e: self.cobertura(e, ini, fin) for e in self.etiquetas}
        maxima = max(coberturas.values(), default=0)
        if maxima > 0:
            candidatos = [e for e, c in coberturas.items() if c == maxima]
            return self._desempatar(candidatos, ini, fin, anterior), "D1" if len(candidatos) == 1 else "D2"
        distancias = {e: self._cercano(e, ini, fin)[0] for e in self.etiquetas}
        minima = min(distancias.values(), default=None)
        if minima is None or minima > HUECO_MAX_MS:
            return None, "sin_turno"
        candidatos = [e for e, d in distancias.items() if d == minima]
        return self._desempatar(candidatos, ini, fin, anterior), "D3"

    def superpuesto(self, ini: int, fin: int) -> int:
        """Milisegundos de [ini, fin) con dos o más etiquetas activas a la vez."""
        eventos = []
        for e in self.etiquetas:
            inicios, fines = self._inicios[e], self._fines[e]
            for k in range(bisect.bisect_right(fines, ini), len(inicios)):
                if inicios[k] >= fin:
                    break
                eventos += [(max(inicios[k], ini), 1), (min(fines[k], fin), -1)]
        eventos.sort()  # en el mismo instante, los fines (−1) van antes: un roce no cuenta
        total, activos, previo = 0, 0, ini
        for t, delta in eventos:
            if activos >= 2:
                total += t - previo
            activos, previo = activos + delta, t
        return total

    def marcas(self, ini: int, fin: int, speaker: str | None) -> tuple[bool, bool]:
        """D5: (overlap, ambiguous) de la intervención [ini, fin)."""
        duracion = fin - ini
        overlap = self.superpuesto(ini, fin) >= OVERLAP_MIN_MS
        if speaker is None:
            return overlap, True
        propia = self.cobertura(speaker, ini, fin)
        otra = max((self.cobertura(e, ini, fin) for e in self.etiquetas if e != speaker), default=0)
        ambiguous = propia * 100 < PROPIO_PCT * duracion or otra * 100 >= SEGUNDO_HABLANTE_PCT * duracion
        return overlap, ambiguous


def _detectados(turnos: Turnos, ini: int, fin: int) -> list[dict]:
    return [{"speaker": e, "name": None} for e in turnos.etiquetas if turnos.cobertura(e, ini, fin) > 0]


def _cerrar(grupo: list[dict], speaker: str | None, turnos: Turnos, seg: dict, indice: int) -> Intervencion:
    start = min(w["start"] for w in grupo)
    end = max(w["end"] for w in grupo)
    overlap, ambiguous = turnos.marcas(ms(start), ms(end), speaker)
    a, b = grupo[0]["char_start"], grupo[-1]["char_end"]
    return Intervencion(start, end, speaker, None, seg["text"][a:b], overlap,
                        ambiguous or any(w["ambiguous"] for w in grupo), "word",
                        _detectados(turnos, ms(start), ms(end)), {"segment": indice, "start": a, "end": b})


def _respaldo(seg: dict, indice: int, turnos: Turnos) -> Intervencion:
    texto = seg["text"]
    a, b = len(texto) - len(texto.lstrip()), len(texto.rstrip())
    fuente = {"segment": indice, "start": a, "end": b}
    intervalo = intervalo_segmento(seg)
    if intervalo is None:
        return Intervencion(None, None, None, None, texto[a:b], None, True, "unknown", None, fuente)
    start, end = intervalo
    ini, fin = ms(start), ms(end)
    detectados = _detectados(turnos, ini, fin)
    speaker = None
    if len(detectados) == 1 and not seg.get("_palabras_fuera_audio"):
        e = detectados[0]["speaker"]
        if turnos.cobertura(e, ini, fin) == fin - ini:
            speaker = e
    overlap, ambiguous = turnos.marcas(ini, fin, speaker)
    return Intervencion(start, end, speaker, None, texto[a:b], overlap, ambiguous, "segment", detectados, fuente)


def armar_intervenciones(asr: dict, turnos: Turnos) -> tuple[list[Intervencion], dict[str, int]]:
    """D1–D5 sobre una partición literal; respaldo íntegro si no es utilizable."""
    intervenciones = []
    conteos = dict.fromkeys(("palabras", "palabras_por_empate", "palabras_por_hueco", "palabras_sin_hablante",
                             "segmentos_respaldo", "segmentos_sin_tiempo"), 0)
    anterior = None
    for indice, seg in enumerate(asr["segments"]):
        palabras = alinear(seg)
        parciales = []
        local = dict.fromkeys(("palabras", "palabras_por_empate", "palabras_por_hueco", "palabras_sin_hablante"), 0)
        previo = anterior
        grupo = []
        if palabras:
            for w in palabras:
                ini, fin = ms(w["start"]), ms(w["end"])
                hablante, regla = turnos.asignar(ini, fin, previo)
                if grupo and hablante != previo:
                    parciales.append(_cerrar(grupo, previo, turnos, seg, indice))
                    grupo = []
                _, ambigua = turnos.marcas(ini, fin, hablante)
                grupo.append({**w, "ambiguous": ambigua or regla in ("D2", "D3")})
                previo = hablante
                local["palabras"] += 1
                local["palabras_por_empate"] += regla == "D2"
                local["palabras_por_hueco"] += regla == "D3"
                local["palabras_sin_hablante"] += hablante is None
            if grupo:
                parciales.append(_cerrar(grupo, previo, turnos, seg, indice))
        # No invertir el orden de las palabras al publicar cambios de hablante.
        if not parciales or any(a.start > b.start for a, b in zip(parciales, parciales[1:])):
            respaldo = _respaldo(seg, indice, turnos)
            intervenciones.append(respaldo)
            anterior = respaldo.speaker
            conteos["segmentos_respaldo"] += 1
            conteos["segmentos_sin_tiempo"] += respaldo.timing == "unknown"
        else:
            intervenciones.extend(parciales)
            anterior = previo
            for k, v in local.items():
                conteos[k] += v
    return intervenciones, conteos


def asociar(carpeta=None, *, audio=None, diarizacion=None, asr=None, salida=None) -> Asociacion:
    rutas = resolver_rutas(carpeta, audio=audio, diarizacion=diarizacion, asr=asr, salida=salida)
    duracion = validar_audio(rutas.audio)

    datos_diar, sha_diar = _leer_json(rutas.diarizacion, "diarizacion")
    violaciones = validar_diarizacion(datos_diar, duracion)
    if violaciones:
        raise AsociacionError("diarizacion", f"{rutas.diarizacion} no cumple el contrato ({len(violaciones)} "
                              f"violaciones; primera: {violaciones[0]})",
                              archivo=rutas.diarizacion, violaciones=violaciones)

    datos_asr, sha_asr = _leer_json(rutas.asr, "asr")
    asr_normal, recortes = validar_asr(datos_asr, duracion, archivo=rutas.asr)
    if not asr_normal["segments"]:
        raise AsociacionError("asr", f"{rutas.asr}: sin habla transcrita, no hay ningún segmento con texto",
                              archivo=rutas.asr)

    turnos = Turnos(datos_diar["segments"])
    intervenciones, conteos = armar_intervenciones(asr_normal, turnos)
    conteos.update({
        "intervenciones": len(intervenciones),
        "intervenciones_sin_hablante": sum(i.speaker is None for i in intervenciones),
        "intervenciones_sin_tiempo": sum(i.timing == "unknown" for i in intervenciones),
        "intervenciones_overlap": sum(i.overlap is True for i in intervenciones),
        "intervenciones_ambiguous": sum(i.ambiguous for i in intervenciones),
    })
    return Asociacion(
        rutas=rutas, duracion=duracion, etiquetas=turnos.etiquetas, turnos=datos_diar["segments"],
        intervenciones=intervenciones,
        sha256={"audio.wav": _sha256_archivo(rutas.audio), "diarization.json": sha_diar, "asr.json": sha_asr},
        recortes_asr=recortes, conteos=conteos, asr=asr_normal,
    )
