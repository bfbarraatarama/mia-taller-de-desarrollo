"""Tareas 2.1 a 2.3: validación de audio.wav, diarization.json y asr.json."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from evaluacion.diarizacion.rutas import RESULTADOS

from .conftest import escribir_wav, segmento
from src.asociacion.contrato import MARGEN_ASR_S, validar_asr, validar_audio, validar_diarizacion
from src.asociacion.errores import AsociacionError

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


def test_diarizacion_de_la_etapa_2():
    from src.diarizacion import contrato as etapa2
    archivos = sorted((RESULTADOS / "hipotesis_S26").glob("*.json"))
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


@pytest.mark.parametrize('inicio,fin,esperado', [
    (0.2001, 0.2002, (0.2, 0.201)),
    (0.1996, 0.2004, (0.199, 0.201)),
    (9.9999, 10.0002, (9.999, 10.0)),
])
def test_asr_externo_intervalo_positivo_no_colapsa(inicio, fin, esperado):
    datos = asr(segmento(('sí', inicio, fin)))
    original = copy.deepcopy(datos)
    normal, recortes = validar_asr(datos, 10.0)
    [seg] = normal['segments']
    [w] = seg['words']
    assert (seg['start'], seg['end']) == (w['start'], w['end']) == esperado
    assert w['word'] == 'sí'
    assert recortes['segmentos_descartados'] == recortes['palabras_descartadas'] == 0
    assert datos == original


def test_asr_fuera_de_grilla_final_no_se_retrotrae():
    # El audio tiene una fracción de ms final sin intervalo representable.
    normal, recortes = validar_asr(asr(segmento(('sí', 10.0001, 10.0002))), 10.00025)
    assert normal['segments'] == []
    assert recortes['segmentos_descartados'] == recortes['palabras_descartadas'] == 1


def test_limite_exacto_de_audio_no_pierde_un_milisegundo():
    datos = asr(segmento(('fin', 1.0, 1.001)))
    normal, recortes = validar_asr(datos, 1.001)
    assert normal == datos
    assert not any(recortes.values())
