"""Pruebas de la evaluación STT: normalización, recorte temporal, sorteo y resultados publicados."""

import json

import pytest

from evaluacion.stt import ejemplos, wer


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("¿Qué TAL, Hermano?", "que tal hermano"),
        ("canción  ñandú", "cancion nandu"),
        ("[No, vos] estás= boluda…", "no vos estas boluda"),
        ("guion-medio ¡ya!", "guionmedio ya"),
        ("   ", ""),
    ],
)
def test_normalize(texto, esperado):
    assert wer.normalize(texto) == esperado


def test_parse_timestamp():
    assert wer.parse_timestamp("00:10:59.979") == pytest.approx(659.979)
    assert wer.parse_timestamp("01:00:00.000") == 3600


def _asr(tmp_path, test_id, segmentos):
    carpeta = tmp_path / test_id
    carpeta.mkdir()
    (carpeta / "asr.json").write_text(
        json.dumps({"language": "es", "segments": segmentos}), encoding="utf-8"
    )


def test_hypothesis_recorta_segmentos_que_empiezan_despues_del_limite(tmp_path):
    _asr(tmp_path, "X", [
        {"start": 0.0, "end": 5.0, "text": "Hola, mundo."},
        {"start": 9.9, "end": 12.0, "text": "Adiós."},  # empieza antes del límite: se conserva
        {"start": 10.0, "end": 14.0, "text": "Sobra"},  # empieza en el límite: se descarta
    ])
    assert wer.load_hypothesis("X", 10.0, base=tmp_path) == "hola mundo adios"
    assert wer.load_hypothesis("X", float("inf"), base=tmp_path) == "hola mundo adios sobra"


def test_wer_de_textos_normalizados():
    ref = wer.normalize("Uno, dos, tres, cuatro.")
    hyp = wer.normalize("uno dos TRES")
    assert wer.word_error_rate(ref, hyp) == pytest.approx(0.25)


def test_seleccion_cordeba_es_determinista_y_respeta_exclusiones():
    a, b = ejemplos.select_cordeba(), ejemplos.select_cordeba()
    assert a == b and len(a) == ejemplos.CORDEBA_K
    numeros = {int(archivo[8:12]) for archivo in a.values()}
    assert not numeros & set(ejemplos.CORDEBA_EXCLUDED)
    assert all(i.startswith("COR-") for i in a)


def test_resultados_versionados_son_consistentes():
    """Cada WER publicado tiene su asr.json publicado, válido y con segmentos."""
    resultados = json.loads((wer.RESULTADOS / wer.ARCHIVO_WER).read_text(encoding="utf-8"))
    assert set(resultados["wer"]) == set(ejemplos.RECORDINGS)
    for test_id in resultados["wer"]:
        asr = json.loads((wer.RESULTADOS_ASR / f"{test_id}.json").read_text(encoding="utf-8"))
        assert asr["language"] == "es" and asr["segments"]
    media = sum(resultados["wer"].values()) / len(resultados["wer"])
    assert resultados["average_wer"] == pytest.approx(media)
