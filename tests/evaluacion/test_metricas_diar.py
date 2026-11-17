"""Tarea 6.2: DER y JER de la diarización (requisito «Métricas de diarización», D10)."""

from __future__ import annotations

import hashlib
import json

import pytest

from evaluacion.diarizacion import der
from evaluacion.diarizacion.referencia import POLITICA_JSON
from evaluacion.modular.metricas_diar import metricas_diarizacion, referencia_tarea

CANAL1 = "0.0\t1.0\t#\n1.0\t3.0\tla oreja\n3.0\t4.0\t#\n6.0\t7.0\t-?\n"
CANAL2 = "0.0\t2.5\tsí <risa>\n2.5\t8.0\t#\n"
FRASES = {"phrases/S22/s22.objects.01.channel1.phrases": CANAL1,
          "phrases/S22/s22.objects.01.channel2.phrases": CANAL2}


def elemento(**cambios):
    e = {"id": "figshare-S22-01", "fuente": "figshare", "sesion": "S22", "tarea": "01", "cuadros": 8 * 16000,
         "modulos": ["stt", "diarizacion", "asociacion", "minutas"],
         "referencia": {"original": "uba_games/figshare-v2/phrases.rar",
                        "entradas": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in FRASES.items()}}}
    return {**e, **cambios}


@pytest.fixture
def frases(monkeypatch):
    monkeypatch.setattr("evaluacion.modular.metricas_diar.leer_miembro",
                        lambda original, entrada: FRASES[entrada].encode())


def test_referencia_de_tarea(frases, tmp_path):
    segmentos = referencia_tarea(elemento(), tmp_path)
    assert segmentos == [
        {"start": 0.0, "end": 2.5, "speaker": "figshare_v2_S22_canal2"},
        {"start": 1.0, "end": 3.0, "speaker": "figshare_v2_S22_canal1"},
        {"start": 6.0, "end": 7.0, "speaker": "figshare_v2_S22_canal1"},  # «-?» es habla según la política
    ]


def test_referencia_con_hash_distinto(frases, tmp_path):
    e = elemento()
    e["referencia"]["entradas"]["phrases/S22/s22.objects.01.channel1.phrases"] = "0" * 64
    with pytest.raises(ValueError, match="channel1"):
        referencia_tarea(e, tmp_path)


def escribir_hipotesis(inferencia, segmentos):
    carpeta = inferencia / "figshare-S22-01"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "diarization.json").write_text(json.dumps({"segments": segmentos}), encoding="utf-8")


def test_misma_configuracion_que_s26(frases, tmp_path):
    escribir_hipotesis(tmp_path / "inf", [{"start": 0.0, "end": 2.5, "speaker": "SPEAKER_01"},
                                          {"start": 1.0, "end": 3.0, "speaker": "SPEAKER_00"},
                                          {"start": 6.0, "end": 7.0, "speaker": "SPEAKER_00"}])
    reporte = metricas_diarizacion([elemento()], tmp_path / "inf", tmp_path)
    tarea = reporte["por_archivo"]["figshare-S22-01"]
    for nombre in der.NOMBRES:
        for clave, valor in der.DEFINICIONES[nombre].items():
            assert tarea[nombre][clave] == valor
        assert tarea[nombre]["incluye_solapamiento"] is True
    assert reporte["politica_etiquetas_sha256"] == hashlib.sha256(POLITICA_JSON.read_bytes()).hexdigest()
    assert tarea["der_estricto"]["valor"] == 0 and tarea["jer"]["valor"] == 0  # etiquetas distintas, mismo reparto
    assert reporte["por_sesion"]["S22"]["der_estricto"]["valor"] == 0
    assert reporte["total"]["der_estricto"]["valor"] == 0


def test_error_conocido_y_faltante(frases, tmp_path):
    escribir_hipotesis(tmp_path / "inf", [{"start": 0.0, "end": 3.0, "speaker": "SPEAKER_00"}])
    otro = elemento(id="figshare-S22-02", tarea="02")
    reporte = metricas_diarizacion([elemento(), otro], tmp_path / "inf", tmp_path)
    assert reporte["por_archivo"]["figshare-S22-01"]["der_estricto"]["valor"] > 0
    assert reporte["faltantes"] == ["figshare-S22-02/diarization.json"]


def test_elemento_sin_referencia(tmp_path):
    e = {"id": "figshare-S22-03", "fuente": "figshare", "sesion": "S22", "modulos": ["diarizacion"]}
    reporte = metricas_diarizacion([e], tmp_path, tmp_path)
    assert reporte["sin_referencia"] == ["figshare-S22-03"] and reporte["total"] is None
