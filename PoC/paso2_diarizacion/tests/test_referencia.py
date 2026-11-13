"""Tareas 6.5 y 6.6: referencia RTTM, validación antes de las métricas e indicador de cobertura (datos sintéticos)."""

import json

import numpy as np
import pytest

from evaluacion import referencia as ref

FS = 16000


def filas(texto: str) -> list:
    """Mismo formato que `leer_anotacion`: (línea, inicio, fin, texto, fin escrito)."""
    salida = []
    for n, linea in enumerate(texto.splitlines(), 1):
        i, f, t = linea.split("\t", 2)
        salida.append((n, float(i), float(f), t.strip(), f))
    return salida


def construir(ch1, ch2="0.0\t1.0\t#\n", cuadros=48000, politica=None):
    return ref.construir({1: filas(ch1), 2: filas(ch2)}, cuadros, FS, politica or {})


# --- tabla del diseño (tarea 6.5) --------------------------------------------------------------------------------

def test_almohadilla_se_excluye_y_se_cuenta():
    r = construir("0.0\t1.0\t#\n1.0\t2.0\thola\n2.0\t3.0\t#\n")
    assert r["segmentos"] == [{"start": 1.0, "end": 2.0, "speaker": "figshare_v2_S26_canal1"}]
    assert r["conteos"]["channel1"]["excluidos_por_almohadilla"] == 2
    assert r["conteos"]["channel2"]["segmentos_referencia"] == 0


@pytest.mark.parametrize("texto", ["eh", "pal-", "¿qué?", "mmm", "o"])
def test_texto_con_letras_es_habla(texto):
    assert len(construir(f"0.5\t1.0\t{texto}\n")["segmentos"]) == 1


def test_etiqueta_sin_clasificar_falla_y_se_lista_con_su_cantidad():
    with pytest.raises(ref.ErrorReferencia, match=r"'-\?' \(2\), '\?-' \(1\)"):
        construir("0.0\t0.5\t-?\n0.5\t1.0\t-?\n1.0\t1.5\thola\n", "0.0\t1.0\t?-\n")


def test_etiqueta_clasificada_como_excluir_no_aparece_y_se_cuenta():
    r = construir("0.0\t0.5\t-?\n1.0\t1.5\thola\n", politica={"-?": "excluir"})
    assert [s["start"] for s in r["segmentos"]] == [1.0]
    assert r["conteos"]["channel1"]["excluidos_por_etiqueta"] == {"-?": 1}


def test_etiqueta_clasificada_como_habla_aparece():
    r = construir("0.0\t0.5\t-?\n", politica={"-?": "habla"})
    assert r["segmentos"] == [{"start": 0.0, "end": 0.5, "speaker": "figshare_v2_S26_canal1"}]


def test_intervalos_del_mismo_canal_superpuestos_o_contiguos_se_unen():
    r = construir("0.0\t1.0\thola\n0.99995\t2.0\tqué tal\n2.0\t2.5\tbien\n")
    assert r["segmentos"] == [{"start": 0.0, "end": 2.5, "speaker": "figshare_v2_S26_canal1"}]
    assert r["conteos"]["channel1"]["uniones"] == 2


def test_solapamiento_entre_canales_se_conserva():
    r = construir("0.0\t2.0\thola\n", "1.0\t3.0\tchau\n")
    assert r["segmentos"] == [{"start": 0.0, "end": 2.0, "speaker": "figshare_v2_S26_canal1"},
                              {"start": 1.0, "end": 3.0, "speaker": "figshare_v2_S26_canal2"}]


def test_fin_dentro_de_la_tolerancia_se_ajusta_y_se_registra():
    r = construir("0.0\t1.0\t#\n1.0\t3.004\thola\n")
    assert r["segmentos"][-1]["end"] == 3.0
    assert r["ajustes_fin"] == [{"canal": 1, "linea": 2, "fin_original_s": 3.004, "fin_original_texto": "3.004",
                                 "fin_ajustado_s": 3.0, "fin_ajustado_cuadros": 48000}]


def test_fin_fuera_de_la_tolerancia_falla():
    with pytest.raises(ref.ErrorReferencia, match="excede"):
        construir("1.0\t3.3\thola\n")


def test_almohadilla_que_excede_no_genera_ajuste():
    assert construir("0.0\t1.0\thola\n1.0\t3.009\t#\n")["ajustes_fin"] == []


def test_fin_que_redondeado_superaria_la_duracion_real():
    cuadros = 836333                    # s26.objects.04: 52,2708125 s
    r = construir("50.0\t52.2706\thola\n", cuadros=cuadros)
    assert round(52.2706, 3) > cuadros / FS   # 52,271 superaría la mezcla
    assert r["segmentos"][0]["end"] == 52.270 and r["ajustes_fin"] == []
    assert ref.validar_referencia(r["segmentos"], cuadros / FS)["utilizable"]


def test_rttm_ordenado_y_releible():
    r = construir("1.0\t2.0\thola\n", "0.5\t1.5\tsí\n1.0\t1.2\t#\n")
    texto = ref.rttm(r["segmentos"], "figshare_v2_S26_objects_04")
    assert texto == ("SPEAKER figshare_v2_S26_objects_04 1 0.500 1.000 <NA> <NA> figshare_v2_S26_canal2 <NA> <NA>\n"
                     "SPEAKER figshare_v2_S26_objects_04 1 1.000 1.000 <NA> <NA> figshare_v2_S26_canal1 <NA> <NA>\n")
    assert ref.leer_rttm(texto) == r["segmentos"]


@pytest.mark.parametrize("contenido, motivo", [({"etiquetas": {"-?": "quizas"}}, "clase"),
                                                ({"etiquetas": {"eh": "habla"}}, "sin letras"),
                                                ({"otra": 1}, "falta el objeto")])
def test_politica_mal_formada(tmp_path, contenido, motivo):
    ruta = tmp_path / "politica.json"
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    with pytest.raises(ref.ErrorReferencia, match=motivo):
        ref.leer_politica(ruta)


def test_politica_versionada_es_valida_y_solo_tiene_las_etiquetas_aprobadas():
    assert ref.leer_politica() == {"-?": "habla", "?-": "habla"}   # decisión del 08/11/2026


# --- validación antes de las métricas (tarea 6.6) ----------------------------------------------------------------

def test_referencia_utilizable():
    r = construir("0.0\t1.0\thola\n", "0.5\t2.0\tsí\n")
    assert ref.validar_referencia(r["segmentos"], 3.0) == {"utilizable": True, "motivo": None}


def test_referencia_sin_habla_deja_las_metricas_en_null():
    r = construir("0.0\t3.0\t#\n", "0.0\t3.0\t#\n")
    v = ref.validar_referencia(r["segmentos"], 3.0)
    assert v == {"utilizable": False, "motivo": "referencia sin habla"}
    nulas = ref.metricas_nulas(v["motivo"])
    assert nulas["der_estricto"] is None and nulas["der_tolerancia"] is None and nulas["jer"] is None
    assert nulas["motivo"] == "referencia sin habla"


@pytest.mark.parametrize("segmentos, motivo", [
    ([{"start": 2.0, "end": 3.5, "speaker": "a"}], "fuera de"),
    ([{"start": 1.0, "end": 1.0, "speaker": "a"}], "fuera de"),
    ([{"start": -0.1, "end": 1.0, "speaker": "a"}], "fuera de"),
    ([{"start": 0.0, "end": 1.0, "speaker": " "}], "hablante vacío"),
    ([{"start": 0.0, "end": 1.0, "speaker": "a"}] * 2, "duplicado"),
])
def test_referencia_no_utilizable(segmentos, motivo):
    v = ref.validar_referencia(segmentos, 3.0)
    assert v["utilizable"] is False and motivo in v["motivo"]


# --- indicador de cobertura (tarea 6.6) --------------------------------------------------------------------------

def _estereo():
    """10 s. Canal 1: habla anotada 0-2 s, tono SIN anotar 6-7 s, otro dentro de la habla del canal 2 (3,5-4,5 s,
    filtración) y un golpe de 0,1 s (8,0-8,1). Canal 2: energía solo dentro de su habla anotada (3-5 s)."""
    rng = np.random.default_rng(11)
    n = 10 * FS
    x = rng.normal(0, 10, (n, 2))
    t = np.arange(n) / FS
    tono = 3000 * np.sin(2 * np.pi * 220 * t)
    for a, b in ((0, 2), (6, 7), (3.5, 4.5), (8.0, 8.1)):
        x[int(a * FS):int(b * FS), 0] += tono[int(a * FS):int(b * FS)]
    x[3 * FS:5 * FS, 1] += rng.normal(0, 3000, 2 * FS)
    anot = {1: filas("0.0\t2.0\thola\n2.0\t10.0\t#\n"), 2: filas("0.0\t3.0\t#\n3.0\t5.0\tsí\n5.0\t10.0\t#\n")}
    return np.clip(x, -32768, 32767).astype(np.int16), anot


def test_cobertura_detecta_un_tono_no_anotado_y_no_la_filtracion():
    estereo, anot = _estereo()
    c = ref.cobertura(estereo, FS, anot, {})
    c1 = c["channel1"]
    assert c1["calculable"] and len(c1["posible_habla_sin_anotar_tramos"]) == 1
    inicio, fin = c1["posible_habla_sin_anotar_tramos"][0]
    assert inicio == pytest.approx(6.0, abs=0.03) and fin == pytest.approx(7.0, abs=0.03)
    assert c1["posible_habla_sin_anotar_s"] == pytest.approx(1.0, abs=0.05)
    assert c1["habla_anotada_energia_baja_proporcion"] < 0.02
    assert c1["umbral_dbfs"] == pytest.approx(c1["piso_dbfs"] + 12.0)
    assert "indicio" in c1["indicio"]


def test_cobertura_sin_habla_sin_anotar_da_cero():
    estereo, anot = _estereo()
    c2 = ref.cobertura(estereo, FS, anot, {})["channel2"]
    assert c2["posible_habla_sin_anotar_s"] == 0 and c2["posible_habla_sin_anotar_tramos"] == []
    assert c2["habla_anotada_energia_baja_proporcion"] < 0.02


def test_cobertura_no_cambia_la_referencia_y_es_determinista():
    estereo, anot = _estereo()
    antes = ref.construir(anot, estereo.shape[0], FS, {})
    assert ref.cobertura(estereo, FS, anot, {}) == ref.cobertura(estereo.copy(), FS, anot, {})
    assert ref.construir(anot, estereo.shape[0], FS, {}) == antes


def test_cobertura_sin_almohadilla_no_es_calculable():
    estereo, _ = _estereo()
    c = ref.cobertura(estereo, FS, {1: filas("0.0\t10.0\thola\n"), 2: filas("0.0\t10.0\t#\n")}, {})
    assert c["channel1"] == {"calculable": False, "motivo": "el canal no tiene intervalos '#'"}
