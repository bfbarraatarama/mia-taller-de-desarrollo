"""Tarea 6.7: preparación completa, manifiesto (contenido / ejecucion) y `--verificar`, sobre una caché sintética."""

import json

import pytest

from evaluacion.preparar_figshare import ErrorPreparacion, contenido_sha256, inventario, preparar, verificar_dataset
from figshare_sintetico import CH1, CH2, armar, huellas

GID = "figshare_v2_S26_objects_04"


@pytest.fixture
def caso(tmp_path, siete_zip):
    def fabricar(anotaciones=None, politica=None):
        cache, extraidos, registro = armar(tmp_path, siete_zip, anotaciones)
        pol = tmp_path / "politica_etiquetas.json"
        pol.write_text(json.dumps({"etiquetas": politica or {}}), encoding="utf-8")
        return {"cache": cache, "extraidos": extraidos, "registro": registro, "politica_json": pol}
    return fabricar


def _preparar(c, carpeta, **extra):
    return preparar(["04"], cache=c["cache"], extraidos=c["extraidos"], registro=c["registro"],
                    politica_json=c["politica_json"], datos=carpeta / "datos", manifiesto=carpeta / "m.json", **extra)


def test_dos_preparaciones_dan_el_mismo_contenido_aunque_cambie_ejecucion(caso, tmp_path):
    c = caso()
    a = _preparar(c, tmp_path / "a", ejecucion_extra={"fecha_hora_utc": "2020-01-01T00:00:00Z"})
    b = _preparar(c, tmp_path / "b", ejecucion_extra={"fecha_hora_utc": "2031-05-05T05:05:05Z",
                                                       "siete_zip": "7-Zip 99.99 simulado"})
    assert a["ejecucion"] != b["ejecucion"]
    ma, mb = (json.loads((tmp_path / d / "m.json").read_text(encoding="utf-8")) for d in ("a", "b"))
    canon = lambda m: json.dumps(m["contenido"], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert canon(ma).encode("utf-8") == canon(mb).encode("utf-8")
    assert ma["contenido_sha256"] == mb["contenido_sha256"] == contenido_sha256(ma["contenido"])
    assert huellas(tmp_path / "a" / "datos") == huellas(tmp_path / "b" / "datos")
    assert (tmp_path / "a" / "m.json").read_bytes().count(b"\r\n") == 0


def test_contenido_del_manifiesto(caso, tmp_path):
    c = caso()
    m = _preparar(c, tmp_path)["contenido"]
    assert m["origen"] == "figshare:22647313:v2" and m["licencia"] == "CC BY 4.0"
    assert m["seleccion"] == ["04"] and m["tolerancias"] == {"fin_s": 0.01, "orden_s": 0.0001}
    assert [o["nombre"] for o in m["originales"]] == ["phrases.rar", "wavs.rar"]
    g, = m["grabaciones"]
    assert g["recording_id"] == GID and g["estado"] == "valida" and g["cuadros_mono"] == g["cuadros_estereo"] == 48000
    assert [a["clave"] for a in g["archivos"]] == ["channel1", "channel1_separado", "channel2", "channel2_separado",
                                                    "wav_completo"]
    assert all(len(a["crc32"]) == 8 and len(a["sha256"]) == 64 for a in g["archivos"])
    assert g["correspondencia"]["channel1"]["con_su_canal"] > 0.99
    assert set(g["cobertura"]) == {"channel1", "channel2"} and g["validacion_referencia"]["utilizable"]
    assert set(g["derivados"]) == {"wav_mono", "rttm"}
    texto = json.dumps(m, ensure_ascii=False)
    assert "hola" not in texto and "buen día" not in texto   # sin el texto de las anotaciones


def test_ajustes_fin_coinciden_con_la_linea_de_la_anotacion(caso, tmp_path):
    c = caso()
    g = _preparar(c, tmp_path)["contenido"]["grabaciones"][0]
    assert g["ajustes_fin"], "CH2 termina 0,004 s después: tiene que haber un ajuste"
    lineas = {1: CH1.splitlines(), 2: CH2.splitlines()}
    for a in g["ajustes_fin"]:
        fin_escrito = lineas[a["canal"]][a["linea"] - 1].split("\t")[1]
        assert a["fin_original_texto"] == fin_escrito and a["fin_original_s"] == float(fin_escrito)
        assert a["fin_ajustado_s"] == 3.0


def test_cambiar_la_politica_cambia_contenido(caso, tmp_path):
    anot = {"04": (CH1.replace("2.5\t3.0\t#", "2.5\t3.0\t-?"), CH2)}
    c = caso(anotaciones=anot, politica={"-?": "habla"})
    a = _preparar(c, tmp_path / "a")
    c["politica_json"].write_text(json.dumps({"etiquetas": {"-?": "excluir"}}), encoding="utf-8")
    b = _preparar(c, tmp_path / "b")
    assert a["contenido_sha256"] != b["contenido_sha256"]
    assert a["contenido"]["politica_etiquetas_sha256"] != b["contenido"]["politica_etiquetas_sha256"]
    assert b["contenido"]["grabaciones"][0]["conteos"]["channel1"]["excluidos_por_etiqueta"] == {"-?": 1}


def test_etiqueta_sin_clasificar_falla_sin_escribir_nada(caso, tmp_path):
    c = caso(anotaciones={"04": (CH1.replace("2.5\t3.0\t#", "2.5\t3.0\t?-"), CH2)})
    inv = inventario(["04"], cache=c["cache"], extraidos=c["extraidos"], registro=c["registro"],
                     politica_json=c["politica_json"])
    assert inv["sin_clasificar"] == ["?-"] and inv["total"]["?-"]["apariciones"] == 1
    with pytest.raises(ErrorPreparacion, match=r"'\?-' \(1\)"):
        _preparar(c, tmp_path / "x")
    assert not (tmp_path / "x").exists()


def test_verificar_falla_nombrando_la_grabacion_si_se_altera_la_mezcla(caso, tmp_path):
    c = caso()
    _preparar(c, tmp_path)
    manifiesto, datos = tmp_path / "m.json", tmp_path / "datos"
    assert verificar_dataset(manifiesto, datos) == [GID]
    doc = json.loads(manifiesto.read_text(encoding="utf-8"))
    doc["ejecucion"]["fecha_hora_utc"] = "1999-12-31T23:59:59Z"   # solo cambia ejecucion: sigue pasando
    manifiesto.write_text(json.dumps(doc), encoding="utf-8")
    assert verificar_dataset(manifiesto, datos) == [GID]
    mezcla = datos / f"{GID}.wav"
    b = bytearray(mezcla.read_bytes())
    b[-1] ^= 0xFF
    mezcla.write_bytes(bytes(b))
    with pytest.raises(ErrorPreparacion, match=rf"{GID}: wav_mono"):
        verificar_dataset(manifiesto, datos)


def test_verificar_detecta_contenido_alterado(caso, tmp_path):
    c = caso()
    _preparar(c, tmp_path)
    doc = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    doc["contenido"]["seleccion"] = ["04", "05"]
    (tmp_path / "m.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ErrorPreparacion, match="contenido_sha256"):
        verificar_dataset(tmp_path / "m.json", tmp_path / "datos")


def test_los_originales_no_cambian(caso, tmp_path):
    c = caso()
    antes = huellas(c["cache"])
    _preparar(c, tmp_path / "salida")
    assert huellas(c["cache"]) == antes


def test_grabacion_excluida_no_genera_derivados(caso, tmp_path):
    c = caso(anotaciones={"04": (CH1.replace("2.5\t3.0\t#", "2.5\t3.3\t#"), CH2)})
    g = _preparar(c, tmp_path)["contenido"]["grabaciones"][0]
    assert g["estado"] == "excluida" and "0.3000 s" in g["motivo"] and "derivados" not in g
    assert not (tmp_path / "datos").exists()
    assert verificar_dataset(tmp_path / "m.json", tmp_path / "datos") == []
