"""Tarea 4.5: línea de comandos en otro proceso (códigos de salida, stderr y --help sin torch)."""

import json
import subprocess
import sys

import pytest

from conftest import MODULO
from resultados import NOMBRE_ERROR, NOMBRE_JSON, NOMBRE_META, escribir_par

SCRIPT = MODULO / "diarizar.py"


def _correr(*args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", cwd=cwd)


def test_audio_invalido(wav):
    r = _correr(wav("48k.wav", hz=48000))
    assert r.returncode == 1
    assert "etapa 'audio'" in r.stderr and "48000 Hz" in r.stderr


def test_audio_inexistente(tmp_path):
    r = _correr(tmp_path / "no_existe.wav")
    assert r.returncode == 1 and "no existe" in r.stderr
    assert not (tmp_path / "no_existe").exists()


def test_parametros_invalidos(wav):
    audio = wav("a.wav")
    assert _correr(audio, "--num-speakers", "0").returncode == 2
    assert _correr(audio, "--device", "tpu").returncode == 2


def _cuda_disponible() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return torch.cuda.is_available()


@pytest.mark.skipif(_cuda_disponible(), reason="hay CUDA: este caso solo se prueba en una máquina sin GPU")
def test_cuda_pedida_sin_gpu(wav):
    audio = wav("a.wav", segundos=2)
    r = _correr(audio, "--device", "cuda")
    assert r.returncode == 1
    assert "etapa 'dispositivo'" in r.stderr
    assert not (audio.parent / "a" / NOMBRE_JSON).exists()


def test_fallo_con_resultado_anterior_presente(wav):
    audio = wav("reunion.wav", hz=48000)  # falla en la validación del audio, en cualquier máquina
    carpeta = audio.parent / "reunion"
    segs = [{"start": 0.0, "end": 0.5, "speaker": "SPEAKER_00"}]
    escribir_par(carpeta, {"segments": segs}, {"run_id": "r-anterior", "segmentos": 1, "hablantes": 1})
    antes = {n: (carpeta / n).read_bytes() for n in (NOMBRE_JSON, NOMBRE_META)}
    r = _correr(audio)
    assert r.returncode != 0
    assert "no usar un diarization.json anterior" in r.stderr
    assert {n: (carpeta / n).read_bytes() for n in (NOMBRE_JSON, NOMBRE_META)} == antes
    error = json.loads((carpeta / NOMBRE_ERROR).read_text(encoding="utf-8"))
    assert error["resultado_anterior_conservado"] is True and error["run_id_anterior"] == "r-anterior"


def test_help_no_importa_torch():
    codigo = (
        "import sys, runpy\n"
        f"sys.path.insert(0, {str(MODULO)!r})\n"
        f"sys.argv = [{str(SCRIPT)!r}, '--help']\n"
        "try:\n"
        f"    runpy.run_path({str(SCRIPT)!r}, run_name='__main__')\n"
        "except SystemExit:\n"
        "    pass\n"
        "print('TORCH_IMPORTADO' if 'torch' in sys.modules or 'pyannote' in sys.modules else 'SIN_TORCH')\n"
    )
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8")
    assert "usage" in r.stdout.lower() or "uso" in r.stdout.lower()
    assert r.stdout.strip().endswith("SIN_TORCH"), r.stdout
