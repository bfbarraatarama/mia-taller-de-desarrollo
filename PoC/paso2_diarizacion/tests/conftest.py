"""Configuración común de las pruebas de la Etapa 2.

- Nivel 1 (sin marker): corre siempre, sin modelo ni GPU.
- Nivel 2 (`slow`), nivel 3a (`calidad`) y nivel 3b (`gpu`): solo con `-m slow` / `-m calidad` / `-m gpu`.
  Sin `-m`, se deseleccionan.
- Cada requisito externo es un fixture que saltea la prueba con un motivo legible si falta.
"""

from __future__ import annotations

import os
import shutil
import sys
import types
import wave
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parents[1]
if str(MODULO) not in sys.path:
    sys.path.insert(0, str(MODULO))

DATASET_POR_DEFECTO = MODULO / "datos" / "figshare_test"


PESADOS = ("slow", "calidad", "gpu")


def pytest_addoption(parser):
    parser.addoption("--diagnostico", action="store_true", default=False,
                     help="nivel 3a: además de la corrida principal, corre la diagnóstica con num_speakers=2")
    parser.addoption("--rehacer", action="store_true", default=False,
                     help="nivel 3a: diariza otra vez aunque haya una corrida anterior compatible")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: nivel 2, integración en CPU con el modelo real (pytest -m slow)")
    config.addinivalue_line("markers", "calidad: nivel 3a, DER y JER con Figshare, en CPU o GPU (pytest -m calidad)")
    config.addinivalue_line("markers", "gpu: nivel 3b, pruebas propias de CUDA (pytest -m gpu)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("markexpr"):
        return
    elegidos, deseleccionados = [], []
    for item in items:
        pesado = any(item.get_closest_marker(m) for m in PESADOS)
        (deseleccionados if pesado else elegidos).append(item)
    if deseleccionados:
        config.hook.pytest_deselected(items=deseleccionados)
        items[:] = elegidos


# --- utilidades ---------------------------------------------------------------------------------------

def escribir_wav(ruta: Path, segundos: float = 1.0, hz: int = 16000, canales: int = 1, ancho: int = 2) -> Path:
    """WAV PCM sintético con un patrón no nulo (determinista)."""
    cuadros = int(round(segundos * hz))
    muestra = bytes((i % 251) for i in range(ancho * canales))
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(canales)
        w.setsampwidth(ancho)
        w.setframerate(hz)
        w.writeframes(muestra * cuadros)
    return ruta


def localizar_7zip() -> str | None:
    candidatos = [os.environ.get("SIETE_ZIP"), shutil.which("7z"), shutil.which("7zz")]
    if os.name == "nt":
        candidatos.append(str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "7-Zip" / "7z.exe"))
    for c in candidatos:
        if c and Path(c).is_file():
            return c
    return None


@pytest.fixture
def wav(tmp_path):
    """Fábrica de WAV sintéticos en tmp_path: wav("a.wav", segundos=10)."""
    def fabricar(nombre="audio.wav", **kwargs):
        return escribir_wav(tmp_path / nombre, **kwargs)
    return fabricar


@pytest.fixture
def sin_token():
    """Quita HF_TOKEN del entorno y lo restaura después (también si lo cargó un .env durante la prueba)."""
    anterior = os.environ.pop("HF_TOKEN", None)
    yield
    if anterior is None:
        os.environ.pop("HF_TOKEN", None)
    else:
        os.environ["HF_TOKEN"] = anterior


@pytest.fixture
def torch_falso(monkeypatch):
    """Reemplaza `torch` por un módulo falso: torch_falso(cuda=True) devuelve el módulo para inspeccionarlo."""
    def instalar(cuda: bool = False):
        torch = types.ModuleType("torch")
        torch.__version__ = "2.8.0+falso"
        torch.device = lambda nombre: nombre
        llamadas = {"empty_cache": 0}

        class OutOfMemoryError(RuntimeError):
            pass

        def empty_cache():
            llamadas["empty_cache"] += 1

        torch.cuda = types.SimpleNamespace(
            is_available=lambda: cuda, empty_cache=empty_cache, reset_peak_memory_stats=lambda: None,
            max_memory_allocated=lambda: 1536 * 2**20, get_device_name=lambda: "GPU falsa",
            OutOfMemoryError=OutOfMemoryError)
        torch.llamadas = llamadas
        monkeypatch.setitem(sys.modules, "torch", torch)
        return torch
    return instalar


# --- requisitos externos (niveles 2 y 3) ----------------------------------------------------------------

@pytest.fixture
def token_hf():
    from entrada import obtener_token
    token = obtener_token()
    if not token:
        pytest.skip("falta HF_TOKEN (en el entorno o en un .env de la carpeta actual)")
    return token


@pytest.fixture
def audios_cpu():
    ruta = os.environ.get("DIARIZACION_AUDIOS_CPU")
    if not ruta:
        pytest.skip("falta DIARIZACION_AUDIOS_CPU (carpeta con las grabaciones de 30 a 60 s del paso 1)")
    carpeta = Path(ruta)
    wavs = sorted(carpeta.glob("*.wav")) if carpeta.is_dir() else []
    if not wavs:
        pytest.skip(f"DIARIZACION_AUDIOS_CPU no tiene WAV: {carpeta}")
    return wavs


@pytest.fixture
def dataset_figshare():
    carpeta = Path(os.environ.get("DIARIZACION_FIGSHARE_DIR") or DATASET_POR_DEFECTO)
    if not carpeta.is_dir() or not any(carpeta.rglob("*.wav")):
        pytest.skip(f"falta el dataset de test preparado en {carpeta} (evaluacion/preparar_figshare.py)")
    return carpeta


@pytest.fixture
def ffmpeg():
    ruta = shutil.which("ffmpeg")
    if not ruta:
        pytest.skip("falta FFmpeg en PATH (ver README, sección FFmpeg)")
    return ruta


@pytest.fixture
def siete_zip():
    ruta = localizar_7zip()
    if not ruta:
        pytest.skip("falta 7-Zip (PATH, %ProgramFiles%\\7-Zip\\7z.exe o variable SIETE_ZIP)")
    return ruta


@pytest.fixture
def cuda():
    try:
        import torch
    except ImportError:
        pytest.skip("sin CUDA: PyTorch no está instalado")
    if not torch.cuda.is_available():
        pytest.skip("sin CUDA: torch.cuda.is_available() es False en esta máquina")
    return torch.cuda.get_device_name()
