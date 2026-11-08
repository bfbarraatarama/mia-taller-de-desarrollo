"""Tareas 3.1 y 3.2: validación de la cabecera del WAV, de num_speakers y obtención del token."""

import os

import pytest

from entrada import MENSAJE_TOKEN_AUSENTE, obtener_token, ocultar_token, validar_audio, validar_num_speakers
from errores import DiarizacionError


def _error(ruta):
    with pytest.raises(DiarizacionError) as e:
        validar_audio(ruta)
    assert e.value.etapa == "audio"
    return e.value.mensaje


def test_wav_valido_devuelve_la_duracion(wav):
    assert validar_audio(wav("ok.wav", segundos=2.5)) == 2.5


def test_wav_inexistente(tmp_path):
    ruta = tmp_path / "no_existe.wav"
    assert str(ruta) in _error(ruta)


def test_wav_estereo(wav):
    mensaje = _error(wav("estereo.wav", canales=2))
    assert "2 canales" in mensaje and "mono" in mensaje


def test_wav_48khz(wav):
    mensaje = _error(wav("48k.wav", hz=48000))
    assert "48000 Hz" in mensaje and "16000 Hz" in mensaje


def test_wav_24_bits(wav):
    mensaje = _error(wav("24bits.wav", ancho=3))
    assert "24 bits" in mensaje and "PCM16" in mensaje


def test_archivo_que_no_es_wav(tmp_path):
    ruta = tmp_path / "texto.wav"
    ruta.write_text("esto no es audio", encoding="utf-8")
    assert "no es un WAV PCM16 legible" in _error(ruta)


def test_wav_sin_muestras(wav):
    assert "no tiene muestras" in _error(wav("vacio.wav", segundos=0))


def test_validar_audio_no_modifica_el_archivo(wav):
    ruta = wav("ok.wav")
    antes = ruta.read_bytes()
    validar_audio(ruta)
    assert ruta.read_bytes() == antes


@pytest.mark.parametrize("valor", [0, -1, True, 2.5, "2"])
def test_num_speakers_invalido(valor):
    with pytest.raises(DiarizacionError) as e:
        validar_num_speakers(valor)
    assert e.value.etapa == "parametros" and "num_speakers" in e.value.mensaje


@pytest.mark.parametrize("valor", [None, 1, 6])
def test_num_speakers_valido(valor):
    validar_num_speakers(valor)


def test_token_del_entorno(sin_token, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("HF_TOKEN=hf_del_archivo\n", encoding="utf-8")
    os.environ["HF_TOKEN"] = "hf_del_entorno"
    assert obtener_token() == "hf_del_entorno"  # el .env no sobrescribe


def test_token_desde_env(sin_token, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("HF_TOKEN=hf_falso_123\n", encoding="utf-8")
    assert obtener_token() == "hf_falso_123"


def test_token_desde_env_en_carpeta_superior(sin_token, monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("HF_TOKEN=hf_superior\n", encoding="utf-8")
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    assert obtener_token() == "hf_superior"


def test_token_ausente(sin_token, monkeypatch, tmp_path):
    vacia = tmp_path / "sin_env"
    vacia.mkdir()
    monkeypatch.chdir(vacia)
    assert obtener_token() is None


def test_mensaje_de_token_ausente_no_tiene_valores():
    assert "HF_TOKEN=..." in MENSAJE_TOKEN_AUSENTE
    assert "hf_" not in MENSAJE_TOKEN_AUSENTE.replace("HF_TOKEN", "")
    assert "huggingface.co/settings/tokens" in MENSAJE_TOKEN_AUSENTE


def test_ocultar_token():
    assert ocultar_token("fallo con hf_secreto en la URL", "hf_secreto") == "fallo con *** en la URL"
    assert ocultar_token("sin token", None) == "sin token"
