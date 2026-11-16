"""Tarea 3.4: audio de la muestra a WAV de 16 kHz, mono y PCM16 (requisito «Audio normalizado»)."""

from __future__ import annotations

import hashlib
import io
import math
import shutil
import struct
import subprocess
import tarfile
import wave
import zipfile
from pathlib import Path

import pytest

from evaluacion.modular.audio import AudioInvalido, leer_miembro, preparar_clip, preparar_tarea_figshare
from evaluacion.modular.config import cargar_config


def wav_bytes(fs: int, muestras: list[int], canales: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(canales)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(struct.pack(f"<{len(muestras)}h", *muestras))
    return buffer.getvalue()


def seno(fs: int, segundos: float) -> list[int]:
    return [int(8000 * math.sin(2 * math.pi * 440 * i / fs)) for i in range(int(fs * segundos))]


def cabecera(ruta: Path) -> tuple[int, int, int, float]:
    with wave.open(str(ruta), "rb") as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth() * 8, w.getnframes() / w.getframerate()


def test_clip_de_openslr(tmp_path):
    original = wav_bytes(48000, seno(48000, 0.5))
    zip_ruta = tmp_path / "es_ar_female.zip"
    with zipfile.ZipFile(zip_ruta, "w") as z:
        z.writestr("arf_00001_00000000001.wav", original)
    registro = preparar_clip(zip_ruta, "arf_00001_00000000001.wav", tmp_path / "clip")
    assert cabecera(tmp_path / "clip" / "audio.wav")[:3] == (16000, 1, 16)
    assert cabecera(tmp_path / "clip" / "audio.wav")[3] == pytest.approx(0.5, abs=0.01)
    assert registro["original_sha256"] == hashlib.sha256(original).hexdigest()
    assert registro["sha256"] == hashlib.sha256((tmp_path / "clip" / "audio.wav").read_bytes()).hexdigest()
    assert "16 kHz" in registro["transformacion"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="falta ffmpeg")
def test_clip_mp3_de_common_voice(tmp_path):
    fuente = tmp_path / "fuente.wav"
    fuente.write_bytes(wav_bytes(48000, seno(48000, 0.5)))
    mp3 = tmp_path / "common_voice_es_1.mp3"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(fuente), str(mp3)], check=True)
    tar_ruta = tmp_path / "cv.tar.gz"
    with tarfile.open(tar_ruta, "w:gz") as t:
        t.add(mp3, arcname="es-Rioplatense/clips/common_voice_es_1.mp3")
    registro = preparar_clip(tar_ruta, "es-Rioplatense/clips/common_voice_es_1.mp3", tmp_path / "clip")
    assert cabecera(tmp_path / "clip" / "audio.wav")[:3] == (16000, 1, 16)
    assert registro["original_sha256"] == hashlib.sha256(mp3.read_bytes()).hexdigest()


def test_mezcla_de_canales(tmp_path, monkeypatch):
    a = [100, -100, 7, 3, 0]
    b = [301, -301, 0, 2]  # un cuadro menos: se tolera (criterio de la Etapa 2)
    miembros = {"c1.wav": wav_bytes(16000, a), "c2.wav": wav_bytes(16000, b)}
    monkeypatch.setattr("evaluacion.modular.audio.leer_miembro", lambda original, entrada: miembros[entrada])
    registro = preparar_tarea_figshare(tmp_path / "wavs.rar", "c1.wav", "c2.wav", tmp_path / "tarea")
    with wave.open(str(tmp_path / "tarea" / "audio.wav"), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getnframes()) == (16000, 1, 4)
        assert list(struct.unpack("<4h", w.readframes(4))) == [200, -201, 3, 2]  # (L + R) // 2
    assert registro["originales_sha256"] == [hashlib.sha256(miembros[k]).hexdigest() for k in ("c1.wav", "c2.wav")]
    assert "(L + R) // 2" in registro["transformacion"]


def test_mezcla_rechaza_canales_desparejos(tmp_path, monkeypatch):
    miembros = {"c1.wav": wav_bytes(16000, [0] * 10), "c2.wav": wav_bytes(16000, [0] * 5)}
    monkeypatch.setattr("evaluacion.modular.audio.leer_miembro", lambda original, entrada: miembros[entrada])
    with pytest.raises(AudioInvalido, match="cuadros"):
        preparar_tarea_figshare(tmp_path / "wavs.rar", "c1.wav", "c2.wav", tmp_path / "tarea")


def test_miembro_inexistente(tmp_path):
    zip_ruta = tmp_path / "a.zip"
    with zipfile.ZipFile(zip_ruta, "w") as z:
        z.writestr("uno.wav", b"x")
    with pytest.raises(AudioInvalido, match="dos.wav"):
        leer_miembro(zip_ruta, "dos.wav")


def test_miembro_de_figshare_real():
    config = cargar_config()
    rar = config.cache / config.originales["figshare_audio"].clave
    if not rar.is_file():
        pytest.skip("falta wavs.rar en hito-2/.cache")
    datos = leer_miembro(rar, "wavs/S22/s22.objects.01.channel1.wav")
    with wave.open(io.BytesIO(datos), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
