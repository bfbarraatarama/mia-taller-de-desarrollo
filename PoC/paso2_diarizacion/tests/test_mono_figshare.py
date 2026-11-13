"""Tarea 6.4: conversión del WAV estéreo a mono (izquierda + derecha) // 2, con datos sintéticos."""

import hashlib
import wave

import numpy as np
import pytest

from entrada import validar_audio
from evaluacion.preparar_figshare import FORMULA_MONO, convertir_a_mono, mezclar_mono
from figshare_sintetico import escribir_wav

IZQ = np.array([-3, 3, 32767, -32768, 1, 0, 7], dtype=np.int32)
DER = np.array([0, -4, 32767, -32768, -2, 0, -8], dtype=np.int32)
ESPERADO = [-2, -1, 32767, -32768, -1, 0, -1]   # división entera hacia abajo, sin desbordar


def test_valores_de_la_mezcla():
    assert mezclar_mono(np.stack([IZQ, DER], axis=1)).tolist() == ESPERADO
    assert "floor_divide" in FORMULA_MONO


def test_conversion_determinista_y_original_intacto(tmp_path):
    rng = np.random.default_rng(3)
    estereo = np.concatenate([np.stack([IZQ, DER], axis=1), rng.integers(-32768, 32768, (16000, 2))])
    original = tmp_path / "s26.objects.04.wav"
    escribir_wav(original, estereo)
    sha_original = hashlib.sha256(original.read_bytes()).hexdigest()

    a = convertir_a_mono(original, tmp_path / "a" / "figshare_v2_S26_objects_04.wav")
    b = convertir_a_mono(original, tmp_path / "b" / "figshare_v2_S26_objects_04.wav")
    assert a == b and a["cuadros"] == estereo.shape[0]
    assert hashlib.sha256(original.read_bytes()).hexdigest() == sha_original

    mono = tmp_path / "a" / "figshare_v2_S26_objects_04.wav"
    assert hashlib.sha256(mono.read_bytes()).hexdigest() == a["sha256"]
    assert validar_audio(mono) == pytest.approx(estereo.shape[0] / 16000)
    with wave.open(str(mono), "rb") as w:
        assert (w.getnchannels(), w.getframerate(), w.getsampwidth(), w.getnframes()) == (1, 16000, 2, 16007)
        muestras = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    assert muestras[:7].tolist() == ESPERADO
    assert np.array_equal(muestras, (estereo[:, 0] + estereo[:, 1]) // 2)
