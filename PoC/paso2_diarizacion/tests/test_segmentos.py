"""Tareas 2.3 y 2.4: normalización de segmentos (design.md §4), casos límite del redondeo y regresión del recorte."""

import json
import math
import random

import pytest

from contrato import validar_diarizacion
from segmentos import TOLERANCIA_FIN_S, acotar, normalizar, techo_3_decimales

D = 197531 / 16000  # 12,3456875 s: más de 3 decimales

# Grabación interrumpida 2026_11_08_11_41_26.wav: 520 000 cuadros a 16 kHz y los 8 turnos crudos de pyannote.
D_INTERRUMPIDA = 520000 / 16000  # 32,5 s
TURNOS_INTERRUMPIDA = [
    (0.3685, 2.3091), (2.4103, 3.2878), (4.0303, 8.9072), (9.3628, 14.4760),
    (14.8641, 19.0491), (19.2685, 21.3947), (22.2553, 24.7866), (26.5922, 32.5997),
]


def _uno(inicio, fin, duracion=D, hablante="SPEAKER_00"):
    return normalizar([(inicio, fin, hablante)], duracion)


# --- tarea 2.4: regresión del recorte -------------------------------------------------------------

def test_regresion_ultimo_tramo_de_la_grabacion_interrumpida():
    segs, corregidos, descartados, exceso = _uno(26.5922, 32.5997, D_INTERRUMPIDA)
    assert segs == [{"start": 26.592, "end": 32.5, "speaker": "SPEAKER_00"}]
    assert (corregidos, descartados) == (1, 0)
    assert exceso == pytest.approx(0.0997, abs=1e-4)
    assert validar_diarizacion({"segments": segs}, D_INTERRUMPIDA) == []


def test_regresion_los_8_turnos_de_la_grabacion_interrumpida():
    turnos = [(s, e, "SPEAKER_00") for s, e in TURNOS_INTERRUMPIDA]
    segs, corregidos, descartados, exceso = normalizar(turnos, D_INTERRUMPIDA)
    assert len(segs) == 8 and (corregidos, descartados) == (1, 0)
    assert segs[-1] == {"start": 26.592, "end": 32.5, "speaker": "SPEAKER_00"}
    assert sum(s["end"] - s["start"] for s in segs) == pytest.approx(27.56, abs=0.01)  # antes quedaban 21,65 s
    assert exceso == pytest.approx(0.0997, abs=1e-4)
    assert validar_diarizacion({"segments": segs}, D_INTERRUMPIDA) == []


def test_exceso_grande_con_inicio_dentro_del_audio_se_recorta():
    segs, corregidos, descartados, exceso = _uno(10.0, D + 0.5)
    assert segs == [{"start": 10.0, "end": 12.345, "speaker": "SPEAKER_00"}]
    assert (corregidos, descartados) == (1, 0)
    assert exceso == pytest.approx(0.5, abs=1e-4)


def test_exceso_por_encima_de_la_tolerancia_heredada_ya_no_descarta():
    # Antes: 0,05 s se corregía y 0,0501 s se descartaba. Ahora los dos se recortan.
    segs, corregidos, descartados, exceso = normalizar(
        [(10.0, D + 0.05, "SPEAKER_00"), (10.0, D + 0.0501, "SPEAKER_01")], D)
    assert [s["speaker"] for s in segs] == ["SPEAKER_00", "SPEAKER_01"]
    assert all(s["end"] == 12.345 for s in segs)
    assert (corregidos, descartados) == (2, 0)
    assert exceso == pytest.approx(0.0501, abs=1e-4)
    assert TOLERANCIA_FIN_S == 0.05  # campo heredado, sin efecto en la decisión


def test_inicio_negativo_se_recorta_a_cero():
    for inicio in (-0.3, -0.06):
        segs, corregidos, descartados, exceso = _uno(inicio, 1.0)
        assert segs == [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]
        assert (corregidos, descartados) == (1, 0)
        assert exceso == 0.0  # el exceso solo mide el final


@pytest.mark.parametrize("inicio, fin", [(D, D + 1.0), (D + 0.001, D + 0.5), (13.0, 14.0), (-1.0, 0.0), (-2.0, -1.0)])
def test_segmento_completamente_fuera_del_audio_se_descarta(inicio, fin):
    segs, corregidos, descartados, exceso = _uno(inicio, fin)
    assert segs == [] and (corregidos, descartados) == (0, 1) and exceso == 0.0


def test_conteos_y_contrato_con_corregidos_y_descartados():
    turnos = [(-0.2, 1.0, "SPEAKER_00"), (11.0, D + 0.3, "SPEAKER_01"), (13.0, 14.0, "SPEAKER_00"),
              (2.0, 3.0, "SPEAKER_01")]
    segs, corregidos, descartados, exceso = normalizar(turnos, D)
    assert (corregidos, descartados) == (2, 1)
    assert exceso == pytest.approx(0.3, abs=1e-4)
    datos = {"segments": segs}
    assert set(datos) == {"segments"} and all(set(s) == {"start", "end", "speaker"} for s in segs)
    assert validar_diarizacion(datos, D) == []


# --- tarea 2.3: casos límite del redondeo (siguen vigentes) ---------------------------------------

def test_techo_nunca_supera_la_duracion():
    assert techo_3_decimales(D) == 12.345
    assert techo_3_decimales(0.3) == 0.3
    assert techo_3_decimales(0.0004) == 0.0
    for cuadros in range(1, 50000, 37):
        d = cuadros / 16000
        assert techo_3_decimales(d) <= d


def test_end_igual_a_la_duracion_se_redondea_hacia_abajo():
    segs, corregidos, descartados, exceso = _uno(10.0, D)
    assert segs == [{"start": 10.0, "end": 12.345, "speaker": "SPEAKER_00"}]
    assert (corregidos, descartados, exceso) == (0, 0, 0.0)
    assert validar_diarizacion({"segments": segs}, D) == []


def test_exceso_pequeno_se_corrige():
    segs, corregidos, descartados, exceso = _uno(10.0, D + 0.0004)
    assert segs[0]["end"] == 12.345
    assert (corregidos, descartados) == (1, 0)
    assert exceso == pytest.approx(0.0004, abs=1e-4)


def test_inicio_que_se_redondea_mas_alla_del_final_se_descarta():
    segs, corregidos, descartados, _ = _uno(12.3455, 12.3456)
    assert segs == []
    assert (corregidos, descartados) == (0, 1)


def test_cero_negativo():
    segs, corregidos, _, _ = _uno(-0.0004, 1.0)
    assert segs[0]["start"] == 0.0
    assert math.copysign(1.0, segs[0]["start"]) == 1.0  # no es -0.0
    assert '"start": 0.0' in json.dumps(segs[0]) and "-0.0" not in json.dumps(segs[0])
    assert corregidos == 1
    assert acotar(-0.0001, 0.5, 1.0) == (0.0, 0.5)


def test_segmento_de_medio_milisegundo_se_descarta():
    segs, _, descartados, _ = _uno(5.0001, 5.0003)  # 0,2 ms: ambos redondean a 5.0
    assert segs == [] and descartados == 1
    segs, _, descartados, _ = _uno(5.0, 5.0004)
    assert segs == [] and descartados == 1


def test_audio_de_menos_de_un_milisegundo():
    duracion = 10 / 16000  # 0,625 ms
    segs, _, descartados, _ = normalizar([(0.0, duracion, "SPEAKER_00"), (0.0001, 0.0005, "SPEAKER_01")], duracion)
    assert segs == [] and descartados == 2
    assert validar_diarizacion({"segments": segs}, duracion) == []


def test_desorden_y_solapamiento():
    turnos = [(5.0, 9.0, "SPEAKER_01"), (0.5, 4.2, "SPEAKER_00"), (3.9, 6.0, "SPEAKER_00"), (3.9, 5.0, "SPEAKER_01")]
    segs, corregidos, descartados, exceso = normalizar(turnos, 10.0)
    assert [(s["start"], s["end"], s["speaker"]) for s in segs] == [
        (0.5, 4.2, "SPEAKER_00"), (3.9, 5.0, "SPEAKER_01"), (3.9, 6.0, "SPEAKER_00"), (5.0, 9.0, "SPEAKER_01")]
    assert (corregidos, descartados, exceso) == (0, 0, 0.0)
    assert validar_diarizacion({"segments": segs}, 10.0) == []


def test_valores_no_finitos_se_descartan():
    segs, _, descartados, _ = normalizar([(float("nan"), 1.0, "A"), (0.0, float("inf"), "A")], 5.0)
    assert segs == [] and descartados == 2


# --- propiedad (2.3 ampliada en 2.4) -------------------------------------------------------------

def test_propiedad_ningun_segmento_fuera_del_audio_y_nada_se_pierde_sin_motivo():
    rng = random.Random(20261107)
    total = 0
    for _ in range(300):
        cuadros = rng.randint(1, 16000 * 600)
        duracion = cuadros / 16000
        d3 = techo_3_decimales(duracion)
        turnos = []
        for _ in range(20):
            if rng.random() < 0.3:  # cerca de los bordes, donde el redondeo y el recorte son delicados
                inicio = rng.choice([duracion, 0.0]) + rng.uniform(-0.6, 0.6)
            else:
                inicio = rng.uniform(-0.6, duracion + 0.6)
            fin = inicio + rng.choice([rng.uniform(0, 0.002), rng.uniform(0, 5)])
            if rng.random() < 0.2:
                fin = duracion + rng.uniform(-0.001, 0.6)
            turnos.append((inicio, fin, f"SPEAKER_{rng.randint(0, 3):02d}"))
        segs, corregidos, descartados, exceso = normalizar(turnos, duracion)
        assert len(segs) + descartados == len(turnos)
        # Se escribe exactamente lo que tiene parte dentro del audio y no queda vacío tras recortar.
        escritos = [(s, e) for s, e, _ in turnos if s < duracion and e > 0 and acotar(s, e, d3) is not None]
        assert len(segs) == len(escritos)
        # exceso_fin_max_s: el mayor exceso entre los recortados por el final que se escriben.
        assert exceso == round(max([e - duracion for _, e in escritos if e > duracion], default=0.0), 4)
        for s in segs:
            assert 0 <= s["start"] < s["end"] <= duracion, (s, duracion)
            assert round(s["start"], 3) == s["start"] and round(s["end"], 3) == s["end"]
        datos = json.loads(json.dumps({"segments": segs}))  # ida y vuelta por JSON sin perder la garantía
        assert validar_diarizacion(datos, duracion) == []
        total += len(turnos)
    assert total == 6000
