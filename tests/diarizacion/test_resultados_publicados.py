"""Resultados versionados de la evaluación de S26 (`evaluacion/diarizacion/resultados/`): coherencia y reproducibilidad.

Nivel 1: no ejecuta pyannote. Si el RTTM local de `datos/figshare_test/S26/` existe y coincide con el manifiesto,
recalcula las métricas desde las hipótesis versionadas y las compara con el reporte.
"""

import hashlib
import json
import os
from pathlib import Path

import pytest

from evaluacion.diarizacion.rutas import DATOS_BASE, MANIFIESTO, RESULTADOS
from evaluacion.diarizacion import der
from evaluacion.diarizacion import referencia as ref

def _cargar(nombre):
    return json.loads((RESULTADOS / nombre).read_text(encoding="utf-8"))


def test_hipotesis_versionadas_coinciden_con_el_reporte():
    s = _cargar("calidad_S26.json")
    validas = {gid: g for gid, g in s["grabaciones"].items() if g["estado"] == "valida"}
    assert len(validas) == 25
    for gid, g in validas.items():
        datos = (RESULTADOS / "hipotesis_S26" / f"{gid}.json").read_bytes()
        assert hashlib.sha256(datos).hexdigest() == g["principal"]["diarization_sha256"], gid


def test_reporte_coherente_con_el_manifiesto_versionado():
    s, m = _cargar("calidad_S26.json"), json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    assert s["parametros"]["manifiesto"]["contenido_sha256"] == m["contenido_sha256"]
    derivados = {g["recording_id"]: g["derivados"] for g in m["contenido"]["grabaciones"]}
    for gid, g in s["grabaciones"].items():
        assert g["wav_mono_sha256"] == derivados[gid]["wav_mono"]["sha256"]
        assert g["rttm_sha256"] == derivados[gid]["rttm"]["sha256"]
        assert g["principal"]["audio_sha256"] == g["wav_mono_sha256"] and g["principal"]["num_speakers"] is None


def test_acumulados_son_la_suma_de_las_grabaciones():
    s, t = _cargar("calidad_S26.json"), _cargar("calidad_total.json")
    filas = [g["principal"]["metricas"] for g in s["grabaciones"].values()]
    for n in ("der_estricto", "der_tolerancia"):
        acc = t["acumulado_total"]["principal"][n]
        comp = sum(f[n]["falsa_alarma_s"] + f[n]["habla_perdida_s"] + f[n]["confusion_s"] for f in filas)
        total = sum(f[n]["total_referencia_s"] for f in filas)
        assert acc["valor"] == pytest.approx(comp / total, abs=1e-5)
        assert acc["total_referencia_s"] == pytest.approx(total, abs=1e-3)
    tabla = t["por_grabacion_ordenadas_por_der_estricto"]["principal"]
    assert [f["der_estricto"] for f in tabla] == sorted(f["der_estricto"] for f in tabla) and len(tabla) == 25


def test_metricas_se_recalculan_desde_las_hipotesis_versionadas():
    m = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    s = _cargar("calidad_S26.json")
    datos = Path(os.environ.get("DIARIZACION_FIGSHARE_DIR") or DATOS_BASE) / m["contenido"]["sesion"]
    grabaciones = m["contenido"]["grabaciones"]
    faltantes = []
    for g in grabaciones:
        rttm = datos / g["derivados"]["rttm"]["ruta"]
        if not rttm.is_file():
            faltantes.append(rttm.name)
        else:
            assert hashlib.sha256(rttm.read_bytes()).hexdigest() == g["derivados"]["rttm"]["sha256"], rttm
    if faltantes:
        pytest.skip(f"faltan {len(faltantes)} referencias RTTM en {datos}; preparar la selección original completa")
    evaluador = der.Evaluador()
    for g in grabaciones:
        rttm = datos / g["derivados"]["rttm"]["ruta"]
        gid = g["recording_id"]
        hip = json.loads((RESULTADOS / "hipotesis_S26" / f"{gid}.json").read_text(encoding="utf-8"))["segments"]
        r = evaluador.evaluar(gid, ref.leer_rttm(rttm.read_text(encoding="utf-8")), hip, g["cuadros_mono"] / g["fs"])
        esperado = s["grabaciones"][gid]["principal"]["metricas"]
        for n in der.NOMBRES:
            assert r[n]["valor"] == esperado[n]["valor"], (gid, n)
        assert r["solapamiento"] == esperado["solapamiento"], gid
    t = _cargar("calidad_total.json")["acumulado_total"]["principal"]
    acc = evaluador.acumulado()
    assert {n: acc[n]["valor"] for n in der.NOMBRES} == {n: t[n]["valor"] for n in der.NOMBRES}
