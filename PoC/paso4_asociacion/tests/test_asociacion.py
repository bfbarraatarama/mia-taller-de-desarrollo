"""Tareas 2.4 y 2.5: asignación (D1), armado de intervenciones (D4) y contrato de transcription.json."""

from __future__ import annotations

import json
import shutil

import pytest

from asociacion import Intervencion, asociar
from conftest import crear_reunion, leer, segmento
from contrato import CAMPOS_INTERVENCION, validar_transcripcion
from errores import AsociacionError
from salida import escribir


def test_happy_path_con_dos_hablantes(reunion):
    a = asociar(reunion)
    hablantes = [i.speaker for i in a.intervenciones]
    assert hablantes == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]
    assert all(not i.overlap and not i.ambiguous for i in a.intervenciones)
    texto = " ".join(i.text for i in a.intervenciones)
    assert texto == "Arrancamos con el presupuesto. De acuerdo. Sigamos. Cerramos acá."


def test_cambio_de_hablante_dentro_de_un_segmento(tmp_path):
    """Whisper corta por pausas, no por hablante: la asignación es por palabra (D1)."""
    carpeta = crear_reunion(tmp_path, 5.0, [(0.0, 2.0, "SPEAKER_00"), (2.0, 4.0, "SPEAKER_01")],
                            [segmento(("Vos", 0.2, 0.6), ("decís", 0.6, 1.9), ("Sí,", 2.1, 2.5), ("claro.", 2.5, 3.0))])
    a = asociar(carpeta)
    assert [(i.speaker, i.text) for i in a.intervenciones] == [("SPEAKER_00", "Vos decís"), ("SPEAKER_01", "Sí, claro.")]


def test_maxima_superposicion(tmp_path):
    """Palabra [2,0–2,4] con SPEAKER_00 hasta 2,1 y SPEAKER_01 desde 2,1: gana SPEAKER_01 (0,3 s contra 0,1 s)."""
    carpeta = crear_reunion(tmp_path, 5.0, [(0.0, 2.1, "SPEAKER_00"), (2.1, 4.0, "SPEAKER_01")],
                            [segmento(("palabra", 2.0, 2.4))])
    assert asociar(carpeta).intervenciones[0].speaker == "SPEAKER_01"


def test_corte_en_cada_segmento_de_whisper(tmp_path):
    """D4: mismo hablante en dos segmentos de Whisper da dos intervenciones."""
    carpeta = crear_reunion(tmp_path, 6.0, [(0.0, 5.0, "SPEAKER_00")],
                            [segmento(("Uno.", 0.5, 1.0)), segmento(("Dos.", 2.0, 2.5))])
    assert [i.text for i in asociar(carpeta).intervenciones] == ["Uno.", "Dos."]


def test_segmento_sin_palabras_como_una_palabra(tmp_path):
    carpeta = crear_reunion(tmp_path, 6.0, [(0.0, 5.0, "SPEAKER_00")], [])
    (carpeta / "asr.json").write_text(json.dumps({"language": "es", "segments": [
        {"start": 1.0, "end": 2.0, "text": " mmm ", "words": []}]}), encoding="utf-8")
    [i] = asociar(carpeta).intervenciones
    assert (i.start, i.end, i.text, i.speaker) == (1.0, 2.0, "mmm", "SPEAKER_00")


@pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="falta espeak-ng en el sistema")
def test_ejemplo_ideal(tmp_path):
    from ejemplo_ideal.generar import generar

    carpeta = generar(tmp_path)
    ref = leer(carpeta / "referencia.json")
    a = asociar(carpeta)
    intervenciones = [(i.start, i.end, i.speaker) for i in a.intervenciones]
    for p in ref["palabras"]:
        [i] = [i for i in intervenciones if i[0] <= p["start"] and p["end"] <= i[1]]
        assert i[2] == p["speaker"], p
    assert sum(len(i.text.split()) for i in a.intervenciones) == len(ref["palabras"])
    assert all(not i.overlap and not i.ambiguous for i in a.intervenciones)


# ---------- 2.5 contrato de salida ----------


def test_campos_exactos(reunion):
    escribir(asociar(reunion))
    datos = leer(reunion / "transcription.json")
    assert set(datos) == {"segments"}
    assert all(tuple(i) == CAMPOS_INTERVENCION for i in datos["segments"])


def test_salida_dentro_del_contrato(reunion):
    a = asociar(reunion)
    escribir(a)
    datos = leer(reunion / "transcription.json")
    assert validar_transcripcion(datos, a.duracion, a.etiquetas) == []


def test_redondeo_y_texto(tmp_path):
    carpeta = crear_reunion(tmp_path, 5.0, [(1.0, 3.0, "SPEAKER_00")], [segmento((" hola", 1.23456, 1.8))])
    [i] = asociar(carpeta).intervenciones
    assert i.start == 1.235 and i.text == "hola"


def test_salida_invalida_detectada(reunion):
    a = asociar(reunion)
    a.intervenciones[1] = Intervencion(start=5.0, end=5.0, speaker="SPEAKER_01", name=None, text="x",
                                       overlap=False, ambiguous=False)
    with pytest.raises(AsociacionError) as e:
        escribir(a)
    assert e.value.paso == "contrato" and "segments[1]" in e.value.mensaje
    assert not (reunion / "transcription.json").exists()


@pytest.mark.parametrize("cambio, regla", [
    (lambda s: s.update(extra=1), "campo"),
    (lambda s: s.update(speaker="SPEAKER_09"), "speaker"),
    (lambda s: s.update(name=""), "name"),
    (lambda s: s.update(text=" hola"), "text"),
    (lambda s: s.update(overlap=0), "overlap"),
    (lambda s: s.update(end=11.0), "duración"),
    (lambda s: s.update(start=1.2345), "decimales"),
])
def test_transcripcion_invalida(cambio, regla):
    s = {"start": 1.0, "end": 2.0, "speaker": "SPEAKER_00", "name": None, "text": "hola",
         "overlap": False, "ambiguous": False}
    cambio(s)
    violaciones = validar_transcripcion({"segments": [s]}, 10.0, {"SPEAKER_00"})
    assert violaciones and regla in " ".join(violaciones)
