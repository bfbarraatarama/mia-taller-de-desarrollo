"""Tarea 7.1: métricas de calidad (DER estricto, DER con tolerancia NIST, JER) sobre casos armados a mano."""

from importlib.metadata import version

import pytest

from conftest import MODULO
from evaluacion import der

A, B = "figshare_v2_S26_canal1", "figshare_v2_S26_canal2"
REF = [{"start": 0.0, "end": 10.0, "speaker": A}, {"start": 10.0, "end": 20.0, "speaker": B}]


def seg(s, e, q):
    return {"start": s, "end": e, "speaker": q}


def evaluar(hip, ref=REF):
    return der.Evaluador().evaluar("g", ref, hip)


def test_der_conocido_por_componente():
    r = evaluar([seg(0, 10, "S0"), seg(10, 15, "S1")])                       # 5 s de habla perdida
    assert r["der_estricto"]["valor"] == pytest.approx(0.25)
    assert r["der_estricto"]["habla_perdida_s"] == pytest.approx(5.0) and r["der_estricto"]["total_referencia_s"] == 20
    r = evaluar([seg(0, 12, "S0"), seg(12, 20, "S1")])                       # 2 s de confusión
    assert r["der_estricto"]["valor"] == pytest.approx(0.10) and r["der_estricto"]["confusion_s"] == pytest.approx(2.0)
    r = evaluar([seg(0, 10, "S0"), seg(10, 20, "S1"), seg(20, 22, "S2")])    # 2 s de falsa alarma
    assert r["der_estricto"]["valor"] == pytest.approx(0.10) and r["der_estricto"]["falsa_alarma_s"] == pytest.approx(2.0)
    assert r["der_tolerancia"]["valor"] > 0 and r["jer"]["valor"] == pytest.approx(0.0)


def test_borde_desplazado_0_2_s_solo_cuenta_en_el_estricto():
    r = evaluar([seg(0, 10.2, "S0"), seg(10.2, 20, "S1")])
    assert r["der_estricto"]["valor"] == pytest.approx(0.2 / 20)
    assert r["der_tolerancia"]["valor"] == 0          # ±0,25 s por lado, no ±0,125 s


def test_borde_desplazado_0_05_s_solo_cuenta_en_el_estricto():
    r = evaluar([seg(0, 10.05, "S0"), seg(10.05, 20, "S1")])
    assert r["der_estricto"]["valor"] > 0 and r["der_tolerancia"]["valor"] == 0


def test_borde_desplazado_0_4_s():
    r = evaluar([seg(0, 10.4, "S0"), seg(10.4, 20, "S1")])
    assert 0 < r["der_tolerancia"]["valor"] < r["der_estricto"]["valor"]


def test_el_solapamiento_cuenta_en_las_dos():
    ref = [seg(0, 10, A), seg(5, 15, B)]
    r = evaluar([seg(0, 10, "S0")], ref)                                     # B nunca detectado, ni en el solapamiento
    assert r["der_estricto"]["total_referencia_s"] == pytest.approx(20.0)   # 5 s de solapamiento cuentan dos veces
    assert r["der_estricto"]["habla_perdida_s"] == pytest.approx(10.0)
    assert r["der_tolerancia"]["valor"] > 0 and r["der_tolerancia"]["habla_perdida_s"] > 0
    perfecta = evaluar([seg(0, 10, "S0"), seg(5, 15, "S1")], ref)
    assert perfecta["der_estricto"]["valor"] == 0 and perfecta["der_tolerancia"]["valor"] == 0


def test_bloques_del_reporte():
    r = evaluar(REF)
    herramienta = f"pyannote.metrics {version('pyannote.metrics')}"
    esperado = {"der_estricto": ("DER", "estricto", 0.0, 0.0), "der_tolerancia": ("DER", "NIST", 0.5, 0.25),
                "jer": ("JER", "estricto", 0.0, 0.0)}
    for nombre, (metrica, criterio, collar, lado) in esperado.items():
        b = r[nombre]
        assert (b["metrica"], b["criterio"], b["collar_pyannote_s"], b["tolerancia_por_lado_s"]) == \
               (metrica, criterio, collar, lado)
        assert b["herramienta"] == herramienta and b["incluye_solapamiento"] is True
    assert "der" not in r
    assert der.COLLAR_NIST_PYANNOTE_S == 2 * der.TOLERANCIA_NIST_POR_LADO_S == 0.5
    readme = (MODULO / "README.md").read_text(encoding="utf-8")
    assert "DER de pyannote.metrics con tolerancia NIST" in readme


def test_jer_perfecto_y_con_un_hablante_mal_asignado():
    r = evaluar([seg(0, 10, "X"), seg(10, 20, "Y")])
    assert r["jer"]["valor"] == 0
    assert r["jer"]["por_hablante_referencia"] == {A: {"hablante_hipotesis": "X", "error": 0.0},
                                                   B: {"hablante_hipotesis": "Y", "error": 0.0}}
    r = evaluar([seg(0, 10, "X"), seg(10, 15, "Y"), seg(15, 20, "X")])     # 5 s de B atribuidos a X
    assert r["jer"]["valor"] > 0
    por = r["jer"]["por_hablante_referencia"]
    assert por[A]["error"] == pytest.approx(5 / 15, abs=1e-6) and por[B]["error"] == pytest.approx(0.5)
    assert r["jer"]["valor"] == pytest.approx((por[A]["error"] + por[B]["error"]) / 2, abs=1e-5)


def test_hablante_de_la_referencia_sin_pareja_tiene_error_1():
    r = evaluar([seg(0, 20, "X")])
    assert sorted(v["error"] for v in r["jer"]["por_hablante_referencia"].values()) == [0.5, 1.0]


@pytest.mark.parametrize("hip", [[seg(0, 12, "S0"), seg(12, 20, "S1"), seg(20, 21, "S2")],
                                 [seg(1, 10.4, "S0"), seg(10.4, 18, "S1"), seg(3, 4, "S1")]])
def test_los_componentes_suman_el_error_total(hip):
    r = evaluar(hip)
    for nombre in ("der_estricto", "der_tolerancia"):
        b = r[nombre]
        suma = b["falsa_alarma_s"] + b["habla_perdida_s"] + b["confusion_s"]
        assert suma / b["total_referencia_s"] == pytest.approx(b["valor"], abs=1e-5)
        assert sum(b["proporciones"].values()) == pytest.approx(b["valor"], abs=1e-5)


def test_acumulado_de_la_sesion_ponderado_por_el_tiempo():
    e = der.Evaluador()
    e.evaluar("g1", REF, [seg(0, 10, "S0"), seg(10, 15, "S1")])                     # 5 de 20 s
    e.evaluar("g2", [seg(0, 40, A)], [seg(0, 40, "S0")])                             # 0 de 40 s
    acc = e.acumulado()
    assert acc["der_estricto"]["valor"] == pytest.approx(5 / 60, abs=1e-6)
    assert acc["der_estricto"]["total_referencia_s"] == pytest.approx(60)
    assert acc["jer"]["grabaciones"] == 2


def test_dispersion_sobre_una_lista_conocida():
    d = der.dispersion({"a": 0.3, "b": 0.1, "c": 0.5, "d": 0.2, "e": 0.4})
    assert (d["q1"], d["mediana"], d["q3"]) == pytest.approx((0.2, 0.3, 0.4))
    assert d["peor"] == {"recording_id": "c", "valor": 0.5} and d["motivo"] is None
    assert d["mejor"] == {"recording_id": "b", "valor": 0.1} and d["n"] == 5
    assert (d["media"], d["minimo"], d["maximo"]) == pytest.approx((0.3, 0.1, 0.5))
    assert d["desviacion_estandar"] == pytest.approx(0.158114, abs=1e-6)   # muestral (n - 1)


def test_dispersion_con_una_sola_grabacion_es_null():
    d = der.dispersion({"a": 0.3})
    assert d["motivo"] == "una sola grabación" and d["n"] == 1
    assert all(d[k] is None for k in ("media", "mediana", "q1", "q3", "minimo", "maximo", "desviacion_estandar",
                                      "mejor", "peor"))


def test_descripcion_de_la_referencia():
    ref = [seg(0, 10, A), seg(5, 15, B)]
    d = der.describir_referencia(ref, 20.0)
    assert d["duracion_audio_s"] == 20 and d["habla_referencia_s"] == 15 and d["habla_superpuesta_s"] == 5
    assert d["habla_referencia_suma_hablantes_s"] == 20 and d["habla_referencia_por_hablante_s"] == {A: 10, B: 10}


@pytest.mark.parametrize("hip", [[seg(0, 12, "S0"), seg(12, 20, "S1"), seg(20, 21, "S2")],
                                 [seg(0, 15, "S0")],
                                 [seg(0, 6, "S0"), seg(6, 15, "S1"), seg(14, 19, "S0")]])
def test_solapamiento_y_resto_suman_el_der_estricto(hip):
    ref = [seg(0, 10, A), seg(5, 15, B), seg(16, 20, A)]
    r = der.Evaluador().evaluar("g", ref, hip, duracion=22.0)
    s, e = r["solapamiento"], r["der_estricto"]
    for k in ("total_referencia_s", "falsa_alarma_s", "habla_perdida_s", "confusion_s"):
        assert s["con_solapamiento"][k] + s["sin_solapamiento"][k] == pytest.approx(e[k], abs=1e-5)
    assert s["con_solapamiento"]["duracion_s"] == 5 and s["con_solapamiento"]["total_referencia_s"] == 10
    assert s["sin_solapamiento"]["duracion_s"] == 17


def test_error_solo_en_el_solapamiento():
    ref = [seg(0, 10, A), seg(5, 15, B)]
    r = der.Evaluador().evaluar("g", ref, [seg(0, 10, "S0"), seg(10, 15, "S1")], duracion=15.0)  # B perdido en 5-10
    s = r["solapamiento"]
    assert s["con_solapamiento"]["habla_perdida_s"] == pytest.approx(5) and s["con_solapamiento"]["der"] == 0.5
    assert s["sin_solapamiento"]["der"] == 0


def test_cobertura_nist_y_uem_explicito():
    r = der.Evaluador().evaluar("g", REF, [seg(0, 10, "S0"), seg(10, 20, "S1"), seg(20, 22, "S2")], duracion=20.0)
    assert r["uem"] == [0.0, 20.0] and r["der_estricto"]["falsa_alarma_s"] == 0   # lo de fuera del audio no cuenta
    c = r["cobertura_nist"]
    assert c["total_referencia_estricto_s"] == 20
    assert c["total_referencia_nist_s"] == pytest.approx(20 - 0.25 - 0.5 - 0.25)  # bordes en 0, 10 y 20
    assert c["proporcion_evaluada"] == pytest.approx(0.95)


def test_acumulado_de_solapamiento_y_agregacion():
    e = der.Evaluador()
    e.evaluar("g1", [seg(0, 10, A), seg(5, 15, B)], [seg(0, 10, "S0"), seg(10, 15, "S1")], duracion=15.0)
    e.evaluar("g2", REF, REF, duracion=20.0)
    acc = e.acumulado()
    assert acc["solapamiento"]["con_solapamiento"]["habla_perdida_s"] == pytest.approx(5)
    assert acc["solapamiento"]["sin_solapamiento"]["der"] == 0
    assert "ponderado" in acc["der_estricto"]["agregacion"]
    assert acc["cobertura_nist"]["total_referencia_estricto_s"] == pytest.approx(40)


def test_cantidad_de_hablantes_que_no_coincide():
    r = evaluar([seg(0, 8, "S0"), seg(8, 12, "S1"), seg(12, 20, "S2")])
    assert r["cantidad_hablantes"] == {"hablantes_referencia": 2, "hablantes_detectados": 3, "cantidad_coincide": False}
    assert der.coincidencias([r["cantidad_hablantes"], {"cantidad_coincide": True}]) == \
           {"grabaciones": 2, "coinciden": 1, "proporcion": 0.5}
