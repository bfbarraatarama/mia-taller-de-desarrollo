"""Tareas 2.1 a 2.3: validación de audio.wav, diarization.json y asr.json."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path

import pytest

from conftest import MODULO, escribir_wav, segmento
from contrato import MARGEN_ASR_S, validar_asr, validar_audio, validar_diarizacion
from errores import AsociacionError

# ---------- 2.1 audio ----------


def test_audio_normalizado(tmp_path):
    assert validar_audio(escribir_wav(tmp_path / "a.wav", 2.5)) == pytest.approx(2.5)


def test_audio_no_normalizado(tmp_path):
    ruta = escribir_wav(tmp_path / "a.wav", 1.0, fs=48000, canales=2)
    with pytest.raises(AsociacionError) as e:
        validar_audio(ruta)
    assert e.value.paso == "audio"
    for texto in ("canales", "esperado 1", "encontrado 2", "frecuencia", "esperado 16000", "encontrado 48000"):
        assert texto in e.value.mensaje


def test_audio_inexistente(tmp_path):
    with pytest.raises(AsociacionError, match="no existe"):
        validar_audio(tmp_path / "falta.wav")


def test_audio_de_24_bits(tmp_path):
    with pytest.raises(AsociacionError, match="bits"):
        validar_audio(escribir_wav(tmp_path / "a.wav", 1.0, ancho=3))


# ---------- 2.2 diarización ----------

DIARIZACION_VALIDA = {"segments": [{"start": 0.5, "end": 3.0, "speaker": "SPEAKER_00"},
                                   {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01"}]}


def test_segmento_despues_del_audio():
    datos = copy.deepcopy(DIARIZACION_VALIDA)
    datos["segments"][1]["end"] = 10.01
    violaciones = validar_diarizacion(datos, 10.0)
    assert len(violaciones) == 1
    assert "segments[1]" in violaciones[0] and "supera la duración" in violaciones[0]


@pytest.mark.parametrize("cambio", [
    lambda d: d.update(extra=1),
    lambda d: d["segments"][0].update(confianza=0.9),
    lambda d: d["segments"][0].pop("speaker"),
    lambda d: d["segments"][0].update(speaker=""),
    lambda d: d["segments"][0].update(start=-0.1),
    lambda d: d["segments"][0].update(end=0.5),
    lambda d: d["segments"][0].update(start=True),
    lambda d: d["segments"].reverse(),
])
def test_diarizacion_invalida(cambio):
    datos = copy.deepcopy(DIARIZACION_VALIDA)
    cambio(datos)
    assert validar_diarizacion(datos, 10.0)


def test_diarizacion_valida_y_vacia():
    assert validar_diarizacion(DIARIZACION_VALIDA, 10.0) == []
    assert validar_diarizacion({"segments": []}, 10.0) == []


def _etapa2() -> Path:
    return Path(os.environ.get("ETAPA2_DIR", MODULO.parent / "paso2_diarizacion"))


@pytest.mark.skipif(not (_etapa2() / "contrato.py").is_file(),
                    reason="falta la Etapa 2 (PR #8); se puede indicar con ETAPA2_DIR")
def test_diarizacion_de_la_etapa_2():
    spec = importlib.util.spec_from_file_location("contrato_etapa2", _etapa2() / "contrato.py")
    etapa2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(etapa2)
    archivos = sorted((_etapa2() / "evaluacion/resultados/hipotesis_S26").glob("*.json"))
    assert len(archivos) == 25
    casos = [json.loads(a.read_text(encoding="utf-8")) for a in archivos]
    # Variantes inválidas, para comparar también los rechazos
    malo = copy.deepcopy(casos[0])
    malo["segments"][-1]["end"] = 1e6
    casos.append(malo)
    for datos in casos:
        duracion = max([s["end"] for s in datos["segments"]], default=0.0)
        duracion = min(duracion, 300.0)
        assert validar_diarizacion(datos, duracion) == etapa2.validar_diarizacion(datos, duracion)


# ---------- 2.3 asr ----------


def asr(*segmentos):
    return {"language": "es", "segments": list(segmentos)}


def test_fin_dentro_del_margen_de_la_etapa_3():
    datos = asr(segmento(("hola", 1.0, 1.5), ("che", 1.5, 10.4)))
    normal, recortes = validar_asr(datos, 10.0)
    seg = normal["segments"][0]
    assert seg["end"] == 10.0 and seg["words"][-1]["end"] == 10.0
    assert recortes["segmentos_recortados"] == 1 and recortes["palabras_recortadas"] == 1
    assert datos["segments"][0]["end"] == 10.4, "la entrada no se modifica"


def test_palabra_que_queda_vacia_tras_el_recorte():
    datos = asr(segmento(("hola", 9.0, 9.8), ("fin", 10.1, 10.6)))
    normal, recortes = validar_asr(datos, 10.0)
    assert [w["word"] for w in normal["segments"][0]["words"]] == ["hola"]
    assert recortes["palabras_descartadas"] == 1


def test_fin_fuera_del_margen_de_la_etapa_3():
    with pytest.raises(AsociacionError) as e:
        validar_asr(asr(segmento(("hola", 9.0, 11.5))), 10.0)
    assert e.value.paso == "asr"
    assert "segments[0]" in e.value.mensaje and f"{MARGEN_ASR_S}" in e.value.mensaje.replace(",", ".")


def test_segmento_sin_palabras():
    normal, _ = validar_asr(asr({"start": 1.0, "end": 2.0, "text": "mmm", "words": []}), 10.0)
    assert normal["segments"][0]["words"] == []


@pytest.mark.parametrize("datos", [
    {"segments": []},
    {"language": "", "segments": []},
    asr({"start": 1.0, "end": 2.0, "text": " ", "words": []}),
    asr({"start": 2.0, "end": 1.0, "text": "x", "words": []}),
    asr({"start": 1.0, "end": 2.0, "text": "x"}),
    asr({"start": 1.0, "end": 2.0, "text": "x", "words": [{"word": "", "start": 1.0, "end": 1.5}]}),
    asr({"start": 1.0, "end": 2.0, "text": "x", "words": [{"word": "x", "start": float("nan"), "end": 1.5}]}),
])
def test_asr_invalido(datos):
    with pytest.raises(AsociacionError):
        validar_asr(datos, 10.0)
