"""Tarea 7.2 — nivel 3a: calidad de la diarización con Figshare (S26), en CPU o GPU (design.md §12).

Para cada grabación válida de la selección del manifiesto, diariza el WAV mono derivado con `device="auto"`:
- corrida `principal`, sin `num_speakers` (como funciona el producto);
- corrida `diagnostico_num_speakers` (`num_speakers=2`), solo con `--diagnostico`.

Comprueba el contrato (A), calcula DER estricto, DER con tolerancia NIST, JER, componentes y cantidad de
hablantes (B), y escribe `tests/reportes/calidad_S26.json` y `tests/reportes/calidad_total.json`.

    python -m pytest PoC/paso2_diarizacion -m calidad -rs                 # solo la principal
    python -m pytest PoC/paso2_diarizacion -m calidad -rs --diagnostico   # además, num_speakers=2
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path

import pytest

from conftest import MODULO
from contrato import validar_diarizacion, validar_par
from evaluacion import der, referencia as ref
from evaluacion.preparar_figshare import DATOS, MANIFIESTO, ErrorPreparacion, verificar_dataset

REPORTES = MODULO / "tests" / "reportes"
CORRIDAS = {"principal": None, "diagnostico_num_speakers": 2}
LIMITACIONES = {
    "referencia": "frases transcritas por canal, no turnos de habla: puede incluir pausas internas y omitir "
                  "expresiones breves no transcritas",
    "acuerdo_entre_anotadores": "no medido",
    "transcripcion_incompleta": "la transcripción de S26 puede estar incompleta: el README de wavs/ indica que "
                                "S26-S30 vienen de annotations_incompleto",
    "hablantes_por_sesion": "2; no evalúa el caso de 3 o más",
    "dominio": "juego colaborativo (UBA Games), no reuniones",
    "interpretacion": "sin umbral: los valores son una línea de base de la PoC; la comparación con DER publicados "
                      "es solo orientativa",
    "der_tolerancia": der.DESCRIPCION_DER_TOLERANCIA,
}


def _manifiesto() -> dict | None:
    try:
        return json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _carpeta_datos(sesion: str) -> Path:
    """`DIARIZACION_FIGSHARE_DIR` (carpeta que contiene `<sesion>/`) o, si no está, `datos/figshare_test/<sesion>`."""
    base = os.environ.get("DIARIZACION_FIGSHARE_DIR")
    return Path(base) / sesion if base else DATOS


@pytest.fixture(scope="module")
def dataset():
    """Manifiesto y derivados verificados (`--verificar`); saltea si el dataset no está preparado."""
    m = _manifiesto()
    contenido = (m or {}).get("contenido", {})
    datos = _carpeta_datos(contenido.get("sesion", "S26"))
    validas = [g for g in contenido.get("grabaciones", []) if g["estado"] == "valida"]
    if not validas or not all((datos / d["ruta"]).is_file() for g in validas for d in g["derivados"].values()):
        pytest.skip(f"falta el dataset de test preparado en {datos} "
                    "(evaluacion/preparar_figshare.py --preparar)")
    try:
        verificar_dataset(MANIFIESTO, datos)
    except ErrorPreparacion as e:
        pytest.fail(f"--verificar falló: {e}")
    return m, datos


@pytest.mark.calidad
def test_calidad_figshare(dataset, token_hf, ffmpeg, request):
    from diarizar import diarizar

    manifiesto, DATOS = dataset
    contenido = manifiesto["contenido"]
    pedidas = ["principal"] + (["diagnostico_num_speakers"] if request.config.getoption("--diagnostico") else [])
    evaluadores = {c: der.Evaluador() for c in pedidas}
    grabaciones = {}
    for g in contenido["grabaciones"]:
        gid = g["recording_id"]
        if g["estado"] != "valida":
            grabaciones[gid] = {"estado": g["estado"], "motivo": g["motivo"]}
            continue
        duracion = g["cuadros_mono"] / g["fs"]
        wav = DATOS / g["derivados"]["wav_mono"]["ruta"]
        segs_ref = ref.leer_rttm((DATOS / g["derivados"]["rttm"]["ruta"]).read_text(encoding="utf-8"))
        validez = ref.validar_referencia(segs_ref, duracion)
        fila = {"estado": "valida", "duracion_s": duracion, "cuadros": g["cuadros_mono"],
                "wav_mono_sha256": g["derivados"]["wav_mono"]["sha256"],
                "rttm_sha256": g["derivados"]["rttm"]["sha256"], "referencia": validez,
                "cobertura": g["cobertura"]}
        for corrida, num in CORRIDAS.items():
            if corrida not in pedidas:
                fila[corrida] = None
                fila[f"{corrida}_motivo"] = "no solicitada"
                continue
            carpeta = REPORTES / "calidad" / gid / corrida
            motivo_reuso = None if request.config.getoption("--rehacer") else \
                reutilizable(carpeta, g["derivados"]["wav_mono"]["sha256"], num)
            if motivo_reuso is None:
                diarizar(wav, salida=carpeta, device="auto", num_speakers=num)
            hip = json.loads((carpeta / "diarization.json").read_text(encoding="utf-8"))
            meta = json.loads((carpeta / "diarization.meta.json").read_text(encoding="utf-8"))
            assert validar_diarizacion(hip, duracion) == [], f"{gid} {corrida}: contrato"   # (A)
            assert validar_par(carpeta / "diarization.json", carpeta / "diarization.meta.json") == []
            assert meta["audio"]["sha256"] == g["derivados"]["wav_mono"]["sha256"]
            bloque = {"num_speakers": num, "dispositivo": meta["dispositivo"], "tiempo_s": meta["tiempo_s"],
                      "run_id": meta["run_id"], "inicio": meta["inicio"], "segmentos": meta["segmentos"],
                      "hablantes_detectados": meta["hablantes"], "modelo": meta["modelo"],
                      "versiones": meta["versiones"], "diarization_sha256": meta["diarization_sha256"],
                      "audio_sha256": meta["audio"]["sha256"],
                      "reutilizada": motivo_reuso is not None, "motivo_reutilizacion": motivo_reuso,
                      "hipotesis": str(carpeta.relative_to(MODULO).as_posix())}
            if validez["utilizable"]:                                                             # (B)
                bloque["metricas"] = evaluadores[corrida].evaluar(gid, segs_ref, hip["segments"], duracion)
            else:
                bloque["metricas"] = ref.metricas_nulas(validez["motivo"])
            fila[corrida] = bloque
        grabaciones[gid] = fila

    evaluadas = {gid: f for gid, f in grabaciones.items() if f.get("principal")}
    assert evaluadas, "ninguna grabación válida para evaluar"
    acumulado = {c: (evaluadores[c].acumulado() if c in pedidas else None) for c in CORRIDAS}
    parametros = {
        "device": "auto", "corridas": {c: {"num_speakers": n} for c, n in CORRIDAS.items()},
        "reutilizacion": "se reutiliza una corrida anterior si es compatible (mismo WAV mono, modelo, versiones, "
                         "num_speakers y dispositivo); --rehacer obliga a diarizar otra vez",
        "dispersion": "estadísticos por grabación, sin ponderar; los acumulados están ponderados por el tiempo",
        "solapamiento": "componentes del DER estricto en las regiones con 2 hablantes o más en la referencia y en el "
                        "resto de [0, duración], con el emparejamiento global fijo",
        "corridas_ejecutadas": pedidas, "uem": "[0, cuadros / 16000] por grabación",
        "metricas": {n: {**der.DEFINICIONES[n], "herramienta": der.HERRAMIENTA, "incluye_solapamiento": True}
                     for n in der.NOMBRES},
        "manifiesto": {"ruta": MANIFIESTO.relative_to(MODULO).as_posix(),
                       "contenido_sha256": manifiesto["contenido_sha256"]},
        "sistema": platform.platform(), "python": platform.python_version(),
    }
    sesion = {"sesion": contenido["sesion"], "seleccion": contenido["seleccion"], "parametros": parametros,
              "grabaciones": grabaciones, "acumulado_sesion": acumulado}
    REPORTES.mkdir(parents=True, exist_ok=True)
    _escribir(REPORTES / f"calidad_{contenido['sesion']}.json", sesion)

    def valores(corrida, metrica):
        return {gid: (f[corrida] or {}).get("metricas", {}).get(metrica, {}).get("valor")
                for gid, f in evaluadas.items() if f.get(corrida) and (f[corrida].get("metricas") or {}).get(metrica)}

    total = {
        "sesiones": [contenido["sesion"]], "parametros": parametros,
        "acumulado_total": acumulado,
        "dispersion": {c: ({m: der.dispersion(valores(c, m)) for m in der.NOMBRES} if c in pedidas else None)
                       for c in CORRIDAS},
        "cantidad_hablantes": {c: (der.coincidencias([f[c]["metricas"]["cantidad_hablantes"] for f in evaluadas.values()
                                                      if f[c]["metricas"].get("cantidad_hablantes")])
                                   if c in pedidas else None) for c in CORRIDAS},
        "dispositivos": sorted({f["principal"]["dispositivo"] for f in evaluadas.values()}),
        "tiempo_inferencia_s": {
            "total": round(sum(f[c]["tiempo_s"] for f in evaluadas.values() for c in pedidas), 3),
            "ejecutada_en_esta_corrida": round(sum(f[c]["tiempo_s"] for f in evaluadas.values() for c in pedidas
                                                   if not f[c]["reutilizada"]), 3),
            "reutilizada": round(sum(f[c]["tiempo_s"] for f in evaluadas.values() for c in pedidas
                                     if f[c]["reutilizada"]), 3),
            "duracion_audio_total_s": round(sum(f["duracion_s"] for f in evaluadas.values()), 3)},
        "excluidas": {gid: f["motivo"] for gid, f in grabaciones.items() if f["estado"] != "valida"},
        "por_grabacion_ordenadas_por_der_estricto": {c: (tabla(evaluadas, c) if c in pedidas else None)
                                                     for c in CORRIDAS},
        "limitaciones": {**LIMITACIONES,
                         "indicador_cobertura": {gid: f["cobertura"] for gid, f in evaluadas.items()}},
    }
    _escribir(REPORTES / "calidad_total.json", total)

    for gid, f in evaluadas.items():
        m = f["principal"]["metricas"]
        assert m.get("der_estricto") is not None, f"{gid}: {m.get('motivo')}"
        for nombre in ("der_estricto", "der_tolerancia"):
            b = m[nombre]
            suma = b["falsa_alarma_s"] + b["habla_perdida_s"] + b["confusion_s"]
            assert suma / b["total_referencia_s"] == pytest.approx(b["valor"], abs=1e-5)
        s = m["solapamiento"]
        for k in ("total_referencia_s", "falsa_alarma_s", "habla_perdida_s", "confusion_s"):
            assert s["con_solapamiento"][k] + s["sin_solapamiento"][k] == pytest.approx(m["der_estricto"][k], abs=1e-4)
        assert s["con_solapamiento"]["duracion_s"] == pytest.approx(m["referencia"]["habla_superpuesta_s"], abs=1e-4)
        assert 0 <= m["jer"]["valor"] <= 1


def tabla(evaluadas: dict, corrida: str) -> list[dict]:
    """Una fila por grabación, ordenada por DER estricto (de menor a mayor)."""
    filas = []
    for gid, f in evaluadas.items():
        m = f[corrida]["metricas"]
        if m.get("der_estricto") is None:
            continue
        e, t, s = m["der_estricto"], m["der_tolerancia"], m["solapamiento"]
        filas.append({
            "recording_id": gid, "duracion_s": round(f["duracion_s"], 3),
            "habla_referencia_s": m["referencia"]["habla_referencia_s"],
            "habla_superpuesta_s": m["referencia"]["habla_superpuesta_s"],
            "hablantes_referencia": m["cantidad_hablantes"]["hablantes_referencia"],
            "hablantes_detectados": m["cantidad_hablantes"]["hablantes_detectados"],
            "der_estricto": e["valor"], "der_tolerancia": t["valor"], "jer": m["jer"]["valor"],
            "estricto_falsa_alarma_s": e["falsa_alarma_s"], "estricto_habla_perdida_s": e["habla_perdida_s"],
            "estricto_confusion_s": e["confusion_s"], "nist_falsa_alarma_s": t["falsa_alarma_s"],
            "nist_habla_perdida_s": t["habla_perdida_s"], "nist_confusion_s": t["confusion_s"],
            "nist_proporcion_evaluada": m["cobertura_nist"]["proporcion_evaluada"],
            "der_con_solapamiento": s["con_solapamiento"]["der"], "der_sin_solapamiento": s["sin_solapamiento"]["der"],
            "tiempo_s": f[corrida]["tiempo_s"], "reutilizada": f[corrida]["reutilizada"]})
    return sorted(filas, key=lambda x: (x["der_estricto"], x["recording_id"]))


def reutilizable(carpeta: Path, sha_mono: str, num_speakers) -> str | None:
    """Motivo para reutilizar una corrida anterior, o None si hay que diarizar.

    Se reutiliza solo si el par JSON/meta es consistente y la corrida es compatible con la actual: mismo WAV mono
    (SHA-256), mismo modelo, mismas versiones de torch y pyannote.audio, mismo `num_speakers`, modo `auto` y el
    mismo dispositivo que elegiría `auto` ahora. Así no se repite una inferencia de CPU de varios minutos.
    """
    import torch
    from importlib.metadata import version

    from diarizar import MODELO
    js, mt = carpeta / "diarization.json", carpeta / "diarization.meta.json"
    if not (js.is_file() and mt.is_file()) or validar_par(js, mt):
        return None
    meta = json.loads(mt.read_text(encoding="utf-8"))
    actual = {"torch": torch.__version__, "pyannote.audio": version("pyannote.audio")}
    compatible = (meta.get("audio", {}).get("sha256") == sha_mono and meta.get("modelo") == MODELO
                  and all(meta.get("versiones", {}).get(k) == v for k, v in actual.items())
                  and meta.get("num_speakers") == num_speakers and meta.get("modo_dispositivo") == "auto"
                  and meta.get("dispositivo") == ("cuda" if torch.cuda.is_available() else "cpu"))
    if not compatible:
        return None
    return (f"corrida {meta['run_id']} reutilizada: mismo WAV mono, modelo {MODELO}, torch {actual['torch']}, "
            f"pyannote.audio {actual['pyannote.audio']}, num_speakers={num_speakers}, {meta['dispositivo']}")


def _escribir(ruta: Path, datos: dict) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
