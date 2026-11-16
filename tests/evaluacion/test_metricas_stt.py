"""Tarea 6.1: WER y CER de la transcripción (requisito «Métricas de transcripción», D10)."""

from __future__ import annotations

import json

import pytest

from evaluacion.modular.metricas_stt import errores, metricas_stt, normalizar, referencia_figshare


def test_normalizacion():
    r = errores(normalizar("Está bien, sí."), normalizar("esta bien si"))
    assert (r["sustituciones"], r["inserciones"], r["borrados"]) == (2, 0, 0)
    assert r["palabras_referencia"] == 3
    assert r["wer"] == pytest.approx(2 / 3)


def test_mayusculas_y_puntuacion_no_son_errores():
    assert errores(normalizar("¿Qué tal? ¡Bien!"), normalizar("que tal bien"))["sustituciones"] == 1  # solo la tilde
    assert errores(normalizar("Mm-hm, OK."), normalizar("mm hm ok"))["wer"] == 0


def test_conteo_de_errores():
    r = errores("a b c d".split(), "a x c d e".split())
    assert (r["sustituciones"], r["inserciones"], r["borrados"]) == (1, 1, 0)
    r = errores("a b c".split(), "a c".split())
    assert (r["sustituciones"], r["inserciones"], r["borrados"]) == (0, 0, 1)
    assert errores([], ["a"])["wer"] is None  # sin referencia no hay WER


def test_cer():
    r = errores(normalizar("casa"), normalizar("caza"))
    assert r["cer"] == pytest.approx(1 / 4)


def test_referencia_figshare_saca_marcas_y_ordena_por_tiempo():
    canal1 = "0.0\t1.0\t#\n1.0\t2.0\teh la m- la oreja\n5.0\t6.0\t-?\n"
    canal2 = "0.5\t1.5\t<risa> está?\n3.0\t4.0\tsí ruedi- rueda\n"
    tokens, excluidos = referencia_figshare(canal1, canal2)
    assert tokens == ["está", "eh", "la", "la", "oreja", "sí", "rueda"]
    assert excluidos == {"etiquetas": 1, "fragmentos": 2, "sin_letras": 1}


def test_metricas_por_fuente(tmp_path, monkeypatch):
    inferencia = tmp_path / "inferencia"
    (inferencia / "clip-a").mkdir(parents=True)
    (inferencia / "clip-a" / "asr.json").write_text(json.dumps(
        {"language": "es", "segments": [{"start": 0, "end": 1, "text": " Hola mundo", "words": []}]}))
    (inferencia / "figshare-S22-01").mkdir(parents=True)
    (inferencia / "figshare-S22-01" / "asr.json").write_text(json.dumps(
        {"language": "es", "segments": [{"start": 0, "end": 1, "text": "está la oreja", "words": []}]}))
    frases = {"c1": "0.6\t1.0\tla oreja\n", "c2": "0.0\t0.5\t<risa> está\n"}
    monkeypatch.setattr("evaluacion.modular.metricas_stt.leer_miembro", lambda original, entrada: frases[entrada].encode())
    elementos = [
        {"id": "clip-a", "fuente": "openslr", "modulos": ["stt"], "referencia": "Hola, mundo."},
        {"id": "figshare-S22-01", "fuente": "figshare", "modulos": ["stt"],
         "referencia": {"original": "uba_games/figshare-v2/phrases.rar", "entradas": {"c1": "x", "c2": "y"}}},
        {"id": "ami-r", "fuente": "ami", "modulos": ["minutas"]},
    ]
    reporte = metricas_stt(elementos, inferencia, tmp_path / "cache", verificar_hash=False)
    assert reporte["por_fuente"]["openslr"]["wer"] == 0
    assert reporte["por_fuente"]["figshare"]["wer"] == 0
    assert reporte["por_fuente"]["figshare"]["excluidos"] == {"etiquetas": 1, "fragmentos": 0, "sin_letras": 0}
    assert reporte["total"]["palabras_referencia"] == 5
    assert set(reporte["por_archivo"]) == {"clip-a", "figshare-S22-01"}


def test_hash_de_la_referencia(tmp_path, monkeypatch):
    monkeypatch.setattr("evaluacion.modular.metricas_stt.leer_miembro", lambda original, entrada: b"0\t1\thola\n")
    (tmp_path / "f").mkdir()
    (tmp_path / "f" / "asr.json").write_text(json.dumps({"language": "es", "segments": []}))
    elemento = {"id": "f", "fuente": "figshare", "modulos": ["stt"],
                "referencia": {"original": "x.rar", "entradas": {"c1": "no-coincide", "c2": "tampoco"}}}
    with pytest.raises(ValueError, match="c1"):
        metricas_stt([elemento], tmp_path, tmp_path)


def test_elemento_sin_referencia(tmp_path):
    reporte = metricas_stt([{"id": "clip-x", "fuente": "openslr", "modulos": ["stt"]}], tmp_path, tmp_path)
    assert reporte["sin_referencia"] == ["clip-x"] and reporte["por_archivo"] == {}
