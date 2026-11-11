"""Tarea 1.2: ejemplo ideal (D10 de design.md).

Comprueba que el generador produce entradas perfectas y consistentes entre sí. El escenario «Ejemplo ideal»
de la spec (100 % de atribución correcta) se prueba en la tarea 2.4, cuando exista la asociación.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import soundfile as sf

pytestmark = pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="falta espeak-ng en el sistema")

ARCHIVOS = ("audio.wav", "diarization.json", "asr.json", "referencia.json")


@pytest.fixture(scope="module")
def ejemplo(tmp_path_factory) -> Path:
    from ejemplo_ideal.generar import generar

    salida = tmp_path_factory.mktemp("ejemplo")
    generar(salida)
    return salida


def leer(carpeta: Path, nombre: str):
    return json.loads((carpeta / nombre).read_text(encoding="utf-8"))


def test_genera_los_cuatro_archivos(ejemplo):
    for nombre in ARCHIVOS:
        assert (ejemplo / nombre).is_file(), nombre


def test_audio_normalizado(ejemplo):
    info = sf.info(ejemplo / "audio.wav")
    assert (info.samplerate, info.channels, info.subtype) == (16000, 1, "PCM_16")


def test_duracion_del_guion(ejemplo):
    assert 55 <= sf.info(ejemplo / "audio.wav").duration <= 80


def test_diarizacion_ideal(ejemplo):
    duracion = sf.info(ejemplo / "audio.wav").duration
    datos = leer(ejemplo, "diarization.json")
    assert set(datos) == {"segments"}
    segs = datos["segments"]
    assert len({s["speaker"] for s in segs}) == 3
    for s in segs:
        assert set(s) == {"start", "end", "speaker"}
        assert 0 <= s["start"] < s["end"] <= duracion
    for a, b in zip(segs, segs[1:]):
        assert a["end"] < b["start"], "el ejemplo ideal no tiene superposiciones"


def test_asr_ideal(ejemplo):
    duracion = sf.info(ejemplo / "audio.wav").duration
    asr = leer(ejemplo, "asr.json")
    assert asr["language"] == "es"
    for seg in asr["segments"]:
        assert seg["text"].strip() == seg["text"] and seg["text"]
        assert 0 <= seg["start"] < seg["end"] <= duracion
        assert seg["text"] == " ".join(w["word"] for w in seg["words"])
        assert seg["words"][0]["start"] == seg["start"] and seg["words"][-1]["end"] == seg["end"]
        for w in seg["words"]:
            assert w["word"].strip() and w["start"] < w["end"]
        for a, b in zip(seg["words"], seg["words"][1:]):
            assert a["end"] <= b["start"]


def test_un_turno_por_intervencion(ejemplo):
    turnos = leer(ejemplo, "diarization.json")["segments"]
    segmentos = leer(ejemplo, "asr.json")["segments"]
    assert [(t["start"], t["end"]) for t in turnos] == [(s["start"], s["end"]) for s in segmentos]


def test_referencia_por_palabra(ejemplo):
    ref = leer(ejemplo, "referencia.json")
    turnos = leer(ejemplo, "diarization.json")["segments"]
    palabras = [w for s in leer(ejemplo, "asr.json")["segments"] for w in s["words"]]
    assert len(ref["palabras"]) == len(palabras)
    for r, w in zip(ref["palabras"], palabras):
        assert (r["word"], r["start"], r["end"]) == (w["word"], w["start"], w["end"])
        turno = next(t for t in turnos if t["start"] <= w["start"] and w["end"] <= t["end"])
        assert r["speaker"] == turno["speaker"]
        assert r["name"] == ref["hablantes"][r["speaker"]]
    assert sorted(ref["hablantes"].values()) == ["Ana", "Carlos", "Sofía"]


def test_cubre_las_ramas_de_D6(ejemplo):
    turnos = leer(ejemplo, "diarization.json")["segments"]
    nombres = leer(ejemplo, "referencia.json")["hablantes"]
    por_nombre = {}
    for t in turnos:
        por_nombre.setdefault(nombres[t["speaker"]], []).append(t["end"] - t["start"])
    assert any(d > 15 for d in por_nombre["Ana"]), "Ana necesita un tramo de más de 15 s (recorte)"
    for nombre in ("Carlos", "Sofía"):
        assert any(5 <= d <= 15 for d in por_nombre[nombre]), f"{nombre} necesita un tramo de 5 a 15 s"


def test_reproducible(ejemplo, tmp_path):
    from ejemplo_ideal.generar import generar

    generar(tmp_path)
    for nombre in ARCHIVOS:
        assert (tmp_path / nombre).read_bytes() == (ejemplo / nombre).read_bytes(), nombre


# ---------- guion de la lista de chequeo manual (tarea 10.1) ----------


@pytest.fixture(scope="module")
def manual(tmp_path_factory) -> Path:
    from ejemplo_ideal.generar import GUION_MANUAL, generar

    return generar(tmp_path_factory.mktemp("manual"), GUION_MANUAL)


def test_intervencion_encima_de_la_anterior(manual):
    """El que interrumpe tiene un solo turno, contenido en el turno anterior; las entradas siguen ordenadas."""
    turnos = leer(manual, "diarization.json")["segments"]
    assert [t["start"] for t in turnos] == sorted(t["start"] for t in turnos)
    assert [s["start"] for s in leer(manual, "asr.json")["segments"]] == [t["start"] for t in turnos]
    por_etiqueta = {}
    for t in turnos:
        por_etiqueta.setdefault(t["speaker"], []).append(t)
    contenidos = [e for e, ts in por_etiqueta.items()
                  if all(any(o["speaker"] != e and o["start"] < t["start"] and t["end"] < o["end"] for o in turnos)
                         for t in ts)]
    assert len(contenidos) == 1


def test_guion_manual_ocho_fichas_y_un_aviso(manual):
    from asociacion import asociar
    from etiquetado import ModeloFichas

    a = asociar(manual)
    m = ModeloFichas(a)
    assert len(m.fichas) == 8
    assert sum(f.aviso_superposicion for f in m.fichas) == 1
    assert any(i.overlap for i in a.intervenciones)
