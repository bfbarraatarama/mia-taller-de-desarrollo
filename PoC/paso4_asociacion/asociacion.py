"""Paso 1 de la API de la Etapa 4 (D7): valida las entradas y asocia palabras con hablantes. No escribe nada.

Implementado (tareas 2.x): D1, asignación por máxima superposición, y D4, intervenciones cortadas por cambio de
hablante y por segmento de Whisper. Pendiente: D2 (empates por continuidad) y D3 (palabras en huecos), tarea 3.1;
D5 (marcas `overlap` y `ambiguous` por cobertura), tarea 3.2. Mientras tanto, un empate se resuelve por la
etiqueta menor, una palabra sin turno queda con `speaker: null` y `ambiguous` solo marca esos casos.

Los tiempos se comparan en milisegundos enteros.
"""

from __future__ import annotations

import bisect
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from contrato import CAMPOS_INTERVENCION, validar_asr, validar_audio, validar_diarizacion
from errores import AsociacionError

NOMBRES_ENTRADA = {"audio": "audio.wav", "diarizacion": "diarization.json", "asr": "asr.json"}


@dataclass
class Intervencion:
    start: float
    end: float
    speaker: str | None
    name: str | None
    text: str
    overlap: bool
    ambiguous: bool

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

    def cobertura(self, etiqueta: str, ini: int, fin: int) -> int:
        """Milisegundos de [ini, fin) cubiertos por los turnos de `etiqueta`."""
        inicios, fines = self._inicios[etiqueta], self._fines[etiqueta]
        total = 0
        for k in range(bisect.bisect_right(fines, ini), len(inicios)):
            if inicios[k] >= fin:
                break
            total += min(fines[k], fin) - max(inicios[k], ini)
        return total

    def asignar(self, ini: int, fin: int) -> str | None:
        """D1: la etiqueta con más cobertura. Empate: la etiqueta menor (D2 llega en la tarea 3.1)."""
        mejor, mejor_cobertura = None, 0
        for etiqueta in self.etiquetas:
            c = self.cobertura(etiqueta, ini, fin)
            if c > mejor_cobertura:
                mejor, mejor_cobertura = etiqueta, c
        return mejor


def _cerrar(grupo: list[dict], speaker: str | None) -> Intervencion:
    return Intervencion(start=grupo[0]["start"], end=grupo[-1]["end"], speaker=speaker, name=None,
                        text=" ".join(w["word"].strip() for w in grupo), overlap=False,
                        ambiguous=speaker is None)


def armar_intervenciones(asr: dict, turnos: Turnos) -> tuple[list[Intervencion], dict[str, int]]:
    """D4: corta por cambio de hablante y en cada segmento de Whisper. Devuelve (intervenciones, conteos)."""
    intervenciones, conteos = [], {"palabras": 0, "palabras_sin_hablante": 0}
    for seg in asr["segments"]:
        palabras = seg["words"] or [{"word": seg["text"], "start": seg["start"], "end": seg["end"]}]
        grupo, actual = [], None
        for w in palabras:
            ini, fin = ms(w["start"]), ms(w["end"])
            hablante = turnos.asignar(ini, max(fin, ini + 1))
            if grupo and hablante != actual:
                intervenciones.append(_cerrar(grupo, actual))
                grupo = []
            grupo.append(w)
            actual = hablante
            conteos["palabras"] += 1
            conteos["palabras_sin_hablante"] += hablante is None
        if grupo:
            intervenciones.append(_cerrar(grupo, actual))
    intervenciones.sort(key=lambda i: i.start)  # estable: respeta el orden de Whisper en empates
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

    turnos = Turnos(datos_diar["segments"])
    intervenciones, conteos = armar_intervenciones(asr_normal, turnos)
    conteos.update({
        "intervenciones": len(intervenciones),
        "intervenciones_sin_hablante": sum(i.speaker is None for i in intervenciones),
        "intervenciones_overlap": sum(i.overlap for i in intervenciones),
        "intervenciones_ambiguous": sum(i.ambiguous for i in intervenciones),
    })
    return Asociacion(
        rutas=rutas, duracion=duracion, etiquetas=turnos.etiquetas, turnos=datos_diar["segments"],
        intervenciones=intervenciones,
        sha256={"audio.wav": _sha256_archivo(rutas.audio), "diarization.json": sha_diar, "asr.json": sha_asr},
        recortes_asr=recortes, conteos=conteos,
    )
