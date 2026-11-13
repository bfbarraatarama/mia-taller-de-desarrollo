"""Métricas de calidad de la diarización (design.md §12, tarea 7.1).

- `der_estricto`: DER de pyannote.metrics con `collar=0.0` (cada borde cuenta).
- `der_tolerancia`: DER de pyannote.metrics con tolerancia NIST de ±0,25 s por borde (`collar=0.5` en pyannote,
  que es el ancho total de la zona excluida). **No** es un resultado de `md-eval`.
- `jer`: Jaccard Error Rate de pyannote.metrics, `collar=0.0`, con el error de cada hablante de la referencia.

Las tres incluyen el habla superpuesta (`skip_overlap=False`). Cada una tiene su propia instancia, acumulada por
sesión (ponderada por el tiempo, como acumula pyannote.metrics). No hay umbral: los valores son una línea de base.
"""

from __future__ import annotations

import statistics
import warnings
from importlib.metadata import version

from pyannote.core import Annotation, Segment, Timeline
from pyannote.metrics.diarization import DiarizationErrorRate, JaccardErrorRate

TOLERANCIA_NIST_POR_LADO_S = 0.25
COLLAR_NIST_PYANNOTE_S = 2 * TOLERANCIA_NIST_POR_LADO_S
HERRAMIENTA = f"pyannote.metrics {version('pyannote.metrics')}"

DEFINICIONES = {
    "der_estricto": {"metrica": "DER", "criterio": "estricto", "collar_pyannote_s": 0.0, "tolerancia_por_lado_s": 0.0},
    "der_tolerancia": {"metrica": "DER", "criterio": "NIST", "collar_pyannote_s": COLLAR_NIST_PYANNOTE_S,
                       "tolerancia_por_lado_s": TOLERANCIA_NIST_POR_LADO_S},
    "jer": {"metrica": "JER", "criterio": "estricto", "collar_pyannote_s": 0.0, "tolerancia_por_lado_s": 0.0},
}
NOMBRES = tuple(DEFINICIONES)
DESCRIPCION_DER_TOLERANCIA = "DER de pyannote.metrics con tolerancia NIST de ±0,25 s por borde (no es md-eval)"


def anotacion(segmentos: list[dict], uri: str = "grabacion") -> Annotation:
    """Annotation de pyannote a partir de [{start, end, speaker}]; conserva los solapamientos."""
    a = Annotation(uri=uri)
    for i, s in enumerate(segmentos):
        a[Segment(float(s["start"]), float(s["end"])), i] = str(s["speaker"])
    return a


def _bloque(nombre: str) -> dict:
    return {**DEFINICIONES[nombre], "herramienta": HERRAMIENTA, "incluye_solapamiento": True}


def _bloque_der(nombre: str, d: dict) -> dict:
    total = float(d["total"])
    comp = {"falsa_alarma_s": float(d["false alarm"]), "habla_perdida_s": float(d["missed detection"]),
            "confusion_s": float(d["confusion"])}
    valor = sum(comp.values()) / total if total else None
    return {**_bloque(nombre), "valor": _r(valor), **{k: _r(v) for k, v in comp.items()},
            "total_referencia_s": _r(total),
            "proporciones": {k[:-2]: _r(v / total) if total else None for k, v in comp.items()}}


def _r(x, n=6):
    return None if x is None else round(float(x), n)


def jer_por_hablante(metrica: JaccardErrorRate, ref: Annotation, hip: Annotation, uem=None) -> dict:
    """Error de cada hablante de la referencia con el mismo emparejamiento óptimo que usa pyannote.metrics."""
    ref_u, hip_u = metrica.uemify(ref, hip, uem=uem, collar=metrica.collar, skip_overlap=metrica.skip_overlap)
    mapeo = metrica.optimal_mapping(hip_u, ref_u)
    salida = {}
    for quien in sorted(ref_u.labels()):
        h_lab = mapeo.get(quien)
        if h_lab is None:
            salida[quien] = {"hablante_hipotesis": None, "error": 1.0}
            continue
        r, h = ref_u.label_timeline(quien), hip_u.label_timeline(h_lab)
        total = r.union(h).support().duration()
        fa = h.duration() - h.crop(r).duration()
        miss = r.duration() - r.crop(h).duration()
        salida[quien] = {"hablante_hipotesis": str(h_lab), "error": _r((fa + miss) / total)}
    return salida


class Evaluador:
    """Acumula las tres métricas de una corrida (principal o diagnóstica) sobre las grabaciones de una sesión."""

    def __init__(self):
        self.der_estricto = DiarizationErrorRate(collar=0.0, skip_overlap=False)
        self.der_tolerancia = DiarizationErrorRate(collar=COLLAR_NIST_PYANNOTE_S, skip_overlap=False)
        self.jer = JaccardErrorRate(collar=0.0, skip_overlap=False)
        self.por_grabacion: dict[str, dict] = {}

    def evaluar(self, recording_id: str, referencia: list[dict], hipotesis: list[dict],
                duracion: float | None = None) -> dict:
        """Métricas de una grabación. Con `duracion`, la región evaluada (UEM) es [0, duracion]; sin ella, la
        unión de las extensiones de referencia e hipótesis (aproximación de pyannote.metrics)."""
        ref, hip = anotacion(referencia, recording_id), anotacion(hipotesis, recording_id)
        uem = Timeline([Segment(0.0, float(duracion))]) if duracion else None
        r = {}
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="'uem' was approximated")
            for nombre in ("der_estricto", "der_tolerancia"):
                r[nombre] = _bloque_der(nombre, getattr(self, nombre)(ref, hip, uem=uem, detailed=True))
            dj = self.jer(ref, hip, uem=uem, detailed=True)
            r["jer"] = {**_bloque("jer"), "valor": _r(dj["jaccard error rate"]),
                        "por_hablante_referencia": jer_por_hablante(self.jer, ref, hip, uem)}
        r["uem"] = [0.0, float(duracion)] if duracion else "unión de las extensiones de referencia e hipótesis"
        estricto, nist = r["der_estricto"]["total_referencia_s"], r["der_tolerancia"]["total_referencia_s"]
        r["cobertura_nist"] = {"total_referencia_estricto_s": estricto, "total_referencia_nist_s": nist,
                               "proporcion_evaluada": _r(nist / estricto) if estricto else None}
        if duracion:
            r["referencia"] = describir_referencia(referencia, duracion)
            r["solapamiento"] = analisis_solapamiento(referencia, hipotesis, duracion)
        r["cantidad_hablantes"] = cantidad_hablantes(referencia, hipotesis)
        self.por_grabacion[recording_id] = r
        return r

    def acumulado(self) -> dict:
        """Valores de la sesión ponderados por el tiempo (componentes sumados), como acumula pyannote.metrics."""
        if not self.por_grabacion:
            return {n: None for n in NOMBRES}
        r = {n: _bloque_der(n, getattr(self, n).accumulated_) for n in ("der_estricto", "der_tolerancia")}
        r["jer"] = {**_bloque("jer"), "valor": _r(abs(self.jer)), "grabaciones": len(self.por_grabacion),
                    "agregacion": "media del error de todos los hablantes de referencia de todas las grabaciones "
                                  "(abs(JaccardErrorRate) de pyannote.metrics)"}
        for n in ("der_estricto", "der_tolerancia"):
            r[n]["agregacion"] = "suma de componentes / suma de total_referencia_s (ponderado por el tiempo)"
        estricto, nist = r["der_estricto"]["total_referencia_s"], r["der_tolerancia"]["total_referencia_s"]
        r["cobertura_nist"] = {"total_referencia_estricto_s": estricto, "total_referencia_nist_s": nist,
                               "proporcion_evaluada": _r(nist / estricto) if estricto else None}
        filas = [g["solapamiento"] for g in self.por_grabacion.values() if "solapamiento" in g]
        if filas:
            r["solapamiento"] = {}
            for region in ("con_solapamiento", "sin_solapamiento"):
                suma = {k: sum(f[region][k] for f in filas) for k in
                        ("duracion_s", "total_referencia_s", "falsa_alarma_s", "habla_perdida_s", "confusion_s")}
                err = suma["falsa_alarma_s"] + suma["habla_perdida_s"] + suma["confusion_s"]
                suma = {k: _r(v) for k, v in suma.items()}
                suma["der"] = _r(err / suma["total_referencia_s"]) if suma["total_referencia_s"] else None
                r["solapamiento"][region] = suma
        return r


def cantidad_hablantes(referencia: list[dict], hipotesis: list[dict]) -> dict:
    n_ref, n_hip = len({s["speaker"] for s in referencia}), len({s["speaker"] for s in hipotesis})
    return {"hablantes_referencia": n_ref, "hablantes_detectados": n_hip, "cantidad_coincide": n_ref == n_hip}


def dispersion(valores: dict[str, float | None]) -> dict:
    """Estadísticos por grabación (sin ponderar) de {recording_id: valor}; null con motivo si hay menos de dos.

    Cuartiles con `statistics.quantiles(method="inclusive")`; desviación estándar muestral (n - 1).
    """
    v = {k: x for k, x in valores.items() if x is not None}
    claves = ("n", "media", "mediana", "q1", "q3", "minimo", "maximo", "desviacion_estandar", "mejor", "peor")
    if len(v) < 2:
        return {**{k: None for k in claves}, "n": len(v),
                "motivo": "una sola grabación" if len(v) == 1 else "sin grabaciones evaluadas"}
    q1, mediana, q3 = statistics.quantiles(sorted(v.values()), n=4, method="inclusive")
    orden = sorted(v, key=lambda k: (v[k], k))
    mejor, peor = orden[0], max(sorted(v), key=lambda k: v[k])
    return {"n": len(v), "media": _r(statistics.fmean(v.values())), "mediana": _r(mediana), "q1": _r(q1),
            "q3": _r(q3), "minimo": _r(v[mejor]), "maximo": _r(v[peor]),
            "desviacion_estandar": _r(statistics.stdev(v.values())),
            "mejor": {"recording_id": mejor, "valor": _r(v[mejor])},
            "peor": {"recording_id": peor, "valor": _r(v[peor])}, "motivo": None}


def describir_referencia(referencia: list[dict], duracion: float) -> dict:
    """Duración del audio, habla de la referencia (unión), suma por hablante y tiempo de habla superpuesta."""
    ref = anotacion(referencia)
    por_hablante = {q: _r(ref.label_duration(q)) for q in sorted(ref.labels())}
    return {"duracion_audio_s": _r(duracion), "habla_referencia_s": _r(ref.get_timeline().support().duration()),
            "habla_referencia_por_hablante_s": por_hablante,
            "habla_referencia_suma_hablantes_s": _r(sum(por_hablante.values())),
            "habla_superpuesta_s": _r(ref.get_overlap().duration())}


def analisis_solapamiento(referencia: list[dict], hipotesis: list[dict], duracion: float) -> dict:
    """Componentes del DER estricto separados en las regiones con y sin habla superpuesta en la referencia.

    Se fija el emparejamiento óptimo global (el del DER estricto de la grabación) y se cuentan los errores con
    `IdentificationErrorRate` (sin volver a optimizar) dentro de cada región. Así las dos regiones suman exactamente
    los componentes del `der_estricto` de la grabación. Regiones: `con_solapamiento` = donde la referencia tiene 2
    hablantes o más; `sin_solapamiento` = el resto de [0, duracion] (incluye silencio de la referencia).
    """
    from pyannote.metrics.identification import IdentificationErrorRate
    ref, hip = anotacion(referencia, "g"), anotacion(hipotesis, "g")
    uem = Timeline([Segment(0.0, float(duracion))])
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="'uem' was approximated")
        mapeo = DiarizationErrorRate(collar=0.0, skip_overlap=False).optimal_mapping(ref, hip, uem=uem)
    hip_m = hip.rename_labels(mapping=mapeo)
    solapada = ref.get_overlap().support()
    regiones = {"con_solapamiento": solapada, "sin_solapamiento": uem.extrude(solapada).support()}
    salida = {"criterio": "der_estricto (collar 0), emparejamiento global fijo", "herramienta": HERRAMIENTA}
    for nombre, region in regiones.items():
        if region.duration() <= 0:
            salida[nombre] = {"duracion_s": 0.0, "total_referencia_s": 0.0, "falsa_alarma_s": 0.0,
                              "habla_perdida_s": 0.0, "confusion_s": 0.0, "der": None}
            continue
        d = IdentificationErrorRate(collar=0.0, skip_overlap=False)(ref, hip_m, uem=region, detailed=True)
        total = float(d["total"])
        error = float(d["false alarm"]) + float(d["missed detection"]) + float(d["confusion"])
        salida[nombre] = {"duracion_s": _r(region.duration()), "total_referencia_s": _r(total),
                          "falsa_alarma_s": _r(d["false alarm"]), "habla_perdida_s": _r(d["missed detection"]),
                          "confusion_s": _r(d["confusion"]), "der": _r(error / total) if total else None}
    return salida


def coincidencias(cantidades: list[dict]) -> dict:
    n = len(cantidades)
    ok = sum(1 for c in cantidades if c["cantidad_coincide"])
    return {"grabaciones": n, "coinciden": ok, "proporcion": _r(ok / n, 4) if n else None}
