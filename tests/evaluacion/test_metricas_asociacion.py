"""Tarea 6.3: atribución de palabras de la asociación (requisito «Atribución de palabras de la asociación», D10)."""

from __future__ import annotations

import json

import pytest

from evaluacion.modular.metricas_asociacion import atribucion, palabras_asignadas
from tests.asociacion.conftest import crear_reunion, segmento

C1, C2 = "figshare_v2_S22_canal1", "figshare_v2_S22_canal2"
# Referencia: canal 1 habla en [0, 3), canal 2 en [2, 6): se superponen en [2, 3).
REFERENCIA = [{"start": 0.0, "end": 3.0, "speaker": C1}, {"start": 2.0, "end": 6.0, "speaker": C2}]


def test_palabra_en_superposicion():
    diar = [{"start": 0.0, "end": 2.5, "speaker": "SPEAKER_00"}, {"start": 2.5, "end": 6.0, "speaker": "SPEAKER_01"}]
    palabras = [(0.5, 1.0, "SPEAKER_00"),   # solo canal 1: bien
                (2.4, 2.6, "SPEAKER_01"),   # los dos canales: cuenta con superposición, bien (canal 2 activo)
                (4.0, 4.5, "SPEAKER_01"),   # solo canal 2: bien
                (7.0, 7.5, "SPEAKER_01")]   # sin habla en la referencia
    r = atribucion(palabras, REFERENCIA, diar, 8.0, [])
    assert r["con_superposicion"] == {"palabras": 1, "correctas": 1, "porcentaje": 100.0}
    assert r["sin_superposicion"] == {"palabras": 2, "correctas": 2, "porcentaje": 100.0}
    assert r["fuera_de_la_referencia"] == 1


def test_correspondencia_de_etiquetas():
    # La diarización llama SPEAKER_00 al participante del canal 2: cuenta el reparto, no el nombre.
    diar = [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_01"}, {"start": 2.0, "end": 6.0, "speaker": "SPEAKER_00"}]
    palabras = [(0.5, 1.0, "SPEAKER_01"), (4.0, 4.5, "SPEAKER_00"), (5.0, 5.5, "SPEAKER_01")]
    r = atribucion(palabras, REFERENCIA, diar, 8.0, [])
    assert r["correspondencia"] == {"SPEAKER_00": C2, "SPEAKER_01": C1}
    assert r["sin_superposicion"] == {"palabras": 3, "correctas": 2, "porcentaje": pytest.approx(66.7)}


def test_palabra_sin_hablante_es_incorrecta():
    diar = [{"start": 0.0, "end": 3.0, "speaker": "SPEAKER_00"}]
    r = atribucion([(1.0, 1.5, None)], REFERENCIA, diar, 8.0, [])
    assert r["sin_superposicion"]["correctas"] == 0 and r["sin_hablante"] == 1


def test_intervenciones_marcadas_sobre_superposicion_real():
    diar = [{"start": 0.0, "end": 6.0, "speaker": "SPEAKER_00"}]
    intervenciones = [{"start": 1.0, "end": 2.5, "overlap": True, "ambiguous": True},    # toca [2, 3)
                      {"start": 4.0, "end": 5.0, "overlap": False, "ambiguous": True},   # no la toca
                      {"start": 2.2, "end": 2.8, "overlap": False, "ambiguous": False}]  # real, sin marca
    r = atribucion([], REFERENCIA, diar, 8.0, intervenciones)
    assert r["intervenciones"] == {"total": 3, "sin_tiempo": 0, "sobre_superposicion_real": 2,
                                   "ambiguous": 2, "ambiguous_sobre_superposicion_real": 1,
                                   "overlap": 1, "overlap_sobre_superposicion_real": 1}


def test_palabras_asignadas_coinciden_con_la_asociacion(tmp_path):
    carpeta = crear_reunion(tmp_path, 4.0, [(0.0, 2.0, "SPEAKER_00"), (1.5, 4.0, "SPEAKER_01")],
                            [segmento(("hola", 0.2, 0.6), ("che", 1.6, 1.9), ("bien", 2.5, 3.0))])
    palabras, respaldo = palabras_asignadas(carpeta)
    assert [p[2] for p in palabras] == ["SPEAKER_00", "SPEAKER_00", "SPEAKER_01"]  # «che»: empate, sigue D2
    assert [p[:2] for p in palabras] == [(0.2, 0.6), (1.6, 1.9), (2.5, 3.0)]
    assert respaldo == {"intervenciones": 0, "palabras": 0}


def test_segmento_por_respaldo_se_cuenta_aparte(tmp_path):
    # Las palabras no reconstruyen el texto del segmento: la asociación usa el segmento entero (respaldo).
    roto = {"start": 0.2, "end": 1.0, "text": "No quiero eso.",
            "words": [{"word": "quiero", "start": 0.4, "end": 0.7}, {"word": "eso.", "start": 0.7, "end": 1.0}]}
    carpeta = crear_reunion(tmp_path, 4.0, [(0.0, 4.0, "SPEAKER_00")],
                            [roto, segmento(("bien", 2.5, 3.0))])
    palabras, respaldo = palabras_asignadas(carpeta)
    assert [p[2] for p in palabras] == ["SPEAKER_00"] and palabras[0][:2] == (2.5, 3.0)
    assert respaldo == {"intervenciones": 1, "palabras": 3}


def test_intervencion_sin_tiempos_se_cuenta_aparte():
    diar = [{"start": 0.0, "end": 6.0, "speaker": "SPEAKER_00"}]
    intervenciones = [{"start": None, "end": None, "overlap": None, "ambiguous": True, "timing": "unknown"},
                      {"start": 2.2, "end": 2.8, "overlap": True, "ambiguous": False, "timing": "word"}]
    r = atribucion([], REFERENCIA, diar, 8.0, intervenciones)["intervenciones"]
    assert r["sin_tiempo"] == 1 and r["total"] == 1
    assert (r["ambiguous"], r["overlap_sobre_superposicion_real"]) == (0, 1)
