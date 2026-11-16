"""Issue #15, grupo 1: entradas fijadas de los escenarios (requisito «Entradas fijadas»)."""

from __future__ import annotations

import io
import json
import math
import struct
import wave
from pathlib import Path

import numpy as np
import pytest

from evaluacion.escenarios.entradas import (EntradaAlterada, agregar_ruido, construir_manifiesto,
                                            verificar_entradas)


def wav_bytes(muestras: np.ndarray, fs: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(muestras.astype("<i2").tobytes())
    return buffer.getvalue()


def leer(datos: bytes) -> np.ndarray:
    with wave.open(io.BytesIO(datos), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)


def seno(segundos: float = 2.0) -> np.ndarray:
    t = np.arange(int(16000 * segundos)) / 16000
    return (6000 * np.sin(2 * math.pi * 300 * t)).astype(np.int16)


def test_ruido_reproducible():
    limpio = wav_bytes(seno())
    a = agregar_ruido(limpio, snr_db=5.0, semilla=20261010)
    b = agregar_ruido(limpio, snr_db=5.0, semilla=20261010)
    c = agregar_ruido(limpio, snr_db=5.0, semilla=7)
    assert a == b and a != c


def test_ruido_con_la_snr_pedida():
    limpio = wav_bytes(seno())
    senal, ruidoso = leer(limpio), leer(agregar_ruido(limpio, snr_db=5.0, semilla=1))
    ruido = ruidoso - senal
    snr = 10 * math.log10(np.mean(senal ** 2) / np.mean(ruido ** 2))
    assert snr == pytest.approx(5.0, abs=0.2)
    with wave.open(io.BytesIO(agregar_ruido(limpio, snr_db=5.0, semilla=1)), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)


def test_ruido_rosa():
    """Más energía en graves que en agudos: la pendiente del espectro es negativa."""
    silencio = wav_bytes(np.zeros(16000 * 4, dtype=np.int16) + 1000)  # señal constante para fijar la escala
    ruido = leer(agregar_ruido(silencio, snr_db=0.0, semilla=3)) - 1000
    espectro = np.abs(np.fft.rfft(ruido)) ** 2
    f = np.fft.rfftfreq(len(ruido), 1 / 16000)
    graves, agudos = espectro[(f > 50) & (f < 200)].mean(), espectro[(f > 4000) & (f < 7000)].mean()
    assert graves > 10 * agudos


def test_entrada_alterada(tmp_path):
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    a.write_bytes(wav_bytes(seno(0.5)))
    b.write_bytes(wav_bytes(seno(0.7)))
    manifiesto = construir_manifiesto({"2.1.2": {"fuentes": [a]}, "2.1.5": {"fuentes": [a, b]}}, raiz=tmp_path)
    ruta = tmp_path / "entradas.manifest.json"
    ruta.write_text(json.dumps(manifiesto), encoding="utf-8")
    assert verificar_entradas(ruta, tmp_path) == []
    b.write_bytes(wav_bytes(seno(0.9)))
    [problema] = verificar_entradas(ruta, tmp_path)
    assert "b.wav" in problema and "2.1.5" in problema
    with pytest.raises(EntradaAlterada, match="b.wav"):
        verificar_entradas(ruta, tmp_path, estricto=True)


def test_orden_de_las_fuentes_se_conserva(tmp_path):
    archivos = []
    for i in (3, 1, 2):
        ruta = tmp_path / f"{i}.wav"
        ruta.write_bytes(wav_bytes(seno(0.1 * i)))
        archivos.append(ruta)
    manifiesto = construir_manifiesto({"2.1.5": {"fuentes": archivos}}, raiz=tmp_path)
    assert [f["ruta"] for f in manifiesto["escenarios"]["2.1.5"]["fuentes"]] == ["3.wav", "1.wav", "2.wav"]
