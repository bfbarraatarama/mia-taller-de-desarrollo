"""Verificación del entorno de la Etapa 2: versiones, importaciones, CPU/GPU, FFmpeg y decodificación.

Uso (con el Python del venv de la etapa):
    python PoC/paso2_diarizacion/verificar_entorno.py                  # WAV sintético
    python PoC/paso2_diarizacion/verificar_entorno.py --wav audio.wav  # además, un WAV real
    python PoC/paso2_diarizacion/verificar_entorno.py --gpu            # exige CUDA (máquinas con GPU)

Cada comprobación imprime OK, AVISO o FALLA. Termina con 0 si no hay ninguna FALLA y con 1 si la hay.
Las versiones esperadas salen de `constraints.txt`: es la única fuente de verdad.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import warnings
import wave
from importlib import metadata
from pathlib import Path

MODULO = Path(__file__).resolve().parent
RESTRICCIONES = MODULO / "constraints.txt"
PYTHON_ESPERADO = (3, 12)
# Dependencias directas: si falta alguna, es FALLA. Las demás del lock pueden no aplicar a la plataforma.
DIRECTAS = ("torch", "torchaudio", "torchcodec", "pyannote.audio", "pyannote.metrics", "python-dotenv", "pytest")
# Instalados que no se fijan en constraints.txt a propósito.
NO_FIJADOS = re.compile(r"^(pip|setuptools|wheel|nvidia-.*|triton)$")
DLL_FFMPEG_POR_DEFECTO = Path(os.environ.get("LOCALAPPDATA", "")) / "ffmpeg7" / "ffmpeg-7.1.1-full_build-shared" / "bin"

_resultados: list[tuple[str, str, str]] = []


def normalizar_nombre(nombre: str) -> str:
    return re.sub(r"[-_.]+", "-", nombre).lower()


def leer_restricciones(ruta: Path = RESTRICCIONES) -> dict[str, str]:
    """{nombre normalizado: especificador} de las líneas `paquete==versión` de constraints.txt."""
    restricciones = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        m = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*(==\s*[^\s;]+)", linea)
        if not m:
            raise ValueError(f"Línea no reconocida en {ruta.name}: {linea!r}")
        restricciones[normalizar_nombre(m[1])] = m[2].replace(" ", "")
    return restricciones


def cumple(instalada: str, especificador: str) -> bool:
    """`2.8.0+cpu` cumple `==2.8.0`; `0.7.0` cumple `==0.7.*` (semántica de PEP 440)."""
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version
    return Version(instalada) in SpecifierSet(especificador)


def informar(estado: str, tema: str, detalle: str) -> None:
    _resultados.append((estado, tema, detalle))
    print(f"[{estado:5}] {tema}: {detalle}")


def verificar_python() -> None:
    v = sys.version_info
    estado = "OK" if (v.major, v.minor) == PYTHON_ESPERADO else "FALLA"
    informar(estado, "Python", f"{platform.python_version()} (se espera {PYTHON_ESPERADO[0]}.{PYTHON_ESPERADO[1]}.x) en {sys.executable}")


def verificar_versiones() -> None:
    restricciones = leer_restricciones()
    instalados = {normalizar_nombre(d.metadata["Name"]): d.version for d in metadata.distributions()}
    distintos, faltan = [], []
    for nombre, espec in sorted(restricciones.items()):
        if nombre not in instalados:
            if nombre in {normalizar_nombre(d) for d in DIRECTAS}:
                faltan.append(nombre)
            continue
        if not cumple(instalados[nombre], espec):
            distintos.append(f"{nombre} {instalados[nombre]} (se espera {espec})")
    for nombre in DIRECTAS:
        clave = normalizar_nombre(nombre)
        if clave in instalados:
            informar("OK" if cumple(instalados[clave], restricciones[clave]) else "FALLA", nombre,
                     f"{instalados[clave]} (constraints: {restricciones[clave]})")
    if faltan:
        informar("FALLA", "dependencias directas", "faltan: " + ", ".join(faltan))
    sobrantes = sorted(n for n in instalados if n not in restricciones and not NO_FIJADOS.match(n))
    if distintos:
        informar("FALLA", "versiones del lock", "; ".join(distintos))
    else:
        informar("OK", "versiones del lock", f"{len(restricciones)} restricciones, todas las instaladas coinciden")
    if sobrantes:
        informar("AVISO", "paquetes fuera del lock", ", ".join(sobrantes))


def verificar_importaciones() -> None:
    for modulo in ("torch", "torchaudio", "torchcodec", "pyannote.audio", "pyannote.metrics", "dotenv", "numpy", "pandas"):
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            try:
                __import__(modulo)
            except Exception as e:  # noqa: BLE001 - se informa cualquier fallo de importación
                informar("FALLA", f"import {modulo}", f"{type(e).__name__}: {str(e)[:200]}")
                continue
        problemas = [str(a.message) for a in avisos if re.search(r"torchcodec|ffmpeg", str(a.message), re.I)]
        if problemas:
            informar("FALLA", f"import {modulo}", "aviso de FFmpeg/torchcodec: " + problemas[0].splitlines()[0][:200])
        else:
            informar("OK", f"import {modulo}", "sin errores")


def verificar_dispositivo(exigir_gpu: bool) -> None:
    try:
        import torch
    except ImportError:
        return
    variante = torch.__version__.partition("+")[2] or "sin etiqueta"
    disponible = torch.cuda.is_available()
    if disponible:
        informar("OK", "dispositivo", f"CUDA disponible: {torch.cuda.get_device_name(0)} (torch {torch.__version__}, "
                                      f"CUDA {torch.version.cuda}); --device auto usará cuda")
    elif exigir_gpu:
        motivo = ("el wheel instalado es de CPU: reinstalar con --index-url .../cu128" if variante == "cpu"
                  else "el wheel es de CUDA pero no hay GPU o driver disponible (revisar nvidia-smi)")
        informar("FALLA", "dispositivo", f"se pidió --gpu y no hay CUDA (torch {torch.__version__}): {motivo}")
    else:
        informar("OK", "dispositivo", f"CPU (torch {torch.__version__}, variante {variante}); --device auto usará cpu")
    if variante.startswith("cu") and not disponible:
        informar("AVISO", "dispositivo", "wheel de CUDA instalado pero CUDA no está disponible")


def verificar_ffmpeg() -> None:
    consola = shutil.which("ffmpeg")
    if consola:
        try:
            primera = subprocess.run([consola, "-hide_banner", "-version"], capture_output=True, text=True,
                                     timeout=20).stdout.splitlines()[0]
        except (OSError, subprocess.SubprocessError, IndexError):
            primera = "no responde"
        informar("OK", "ffmpeg en PATH (consola)", f"{primera} — informativo: torchcodec usa sus propias bibliotecas")
    else:
        informar("AVISO", "ffmpeg en PATH (consola)", "no hay ffmpeg en PATH (no lo necesita torchcodec, sí la Etapa 1)")
    if os.name != "nt":
        return
    pth = [p for p in map(Path, sys.path) if (p / "ffmpeg_dll_dir.pth").is_file()]
    carpeta = Path(os.environ.get("DIARIZACION_FFMPEG_DLL_DIR") or DLL_FFMPEG_POR_DEFECTO)
    if not pth:
        informar("FALLA", "FFmpeg para torchcodec", "falta ffmpeg_dll_dir.pth en site-packages del venv (ver README)")
    dlls = sorted(p.name for p in carpeta.glob("avcodec-*.dll")) if carpeta.is_dir() else []
    if dlls:
        informar("OK", "FFmpeg para torchcodec", f"{carpeta} ({', '.join(dlls)})")
    else:
        informar("FALLA", "FFmpeg para torchcodec", f"no hay avcodec-*.dll en {carpeta} (FFmpeg 7.1.1 shared, ver README)")


def _wav_sintetico(ruta: Path) -> None:
    import math
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(int(8000 * math.sin(2 * math.pi * 440 * i / 16000)).to_bytes(2, "little", signed=True)
                               for i in range(16000)))


def verificar_decodificacion(wav_real: Path | None) -> None:
    rutas = []
    with tempfile.TemporaryDirectory() as tmp:
        sintetico = Path(tmp) / "sintetico_16k.wav"
        _wav_sintetico(sintetico)
        rutas.append(("WAV sintético", sintetico))
        if wav_real:
            rutas.append((f"WAV {wav_real.name}", wav_real))
        for nombre, ruta in rutas:
            try:
                with wave.open(str(ruta), "rb") as w:
                    cuadros, hz, canales = w.getnframes(), w.getframerate(), w.getnchannels()
                from torchcodec.decoders import AudioDecoder
                muestras = AudioDecoder(str(ruta)).get_all_samples()
                n = muestras.data.shape[-1]
            except Exception as e:  # noqa: BLE001
                informar("FALLA", f"decodificación ({nombre})", f"{type(e).__name__}: {str(e).splitlines()[0][:200]}")
                continue
            completo = n == cuadros and muestras.sample_rate == hz
            formato = "" if (hz, canales) == (16000, 1) else f" — AVISO: {hz} Hz, {canales} canales (la Etapa 2 exige 16 kHz mono)"
            informar("OK" if completo else "FALLA", f"decodificación ({nombre})",
                     f"torchcodec leyó {n} muestras a {muestras.sample_rate} Hz; la cabecera declara {cuadros}{formato}")


def verificar_token() -> None:
    sys.path.insert(0, str(MODULO))
    from entrada import obtener_token
    if obtener_token():
        informar("OK", "token de Hugging Face", "configurado (no se muestra)")
    else:
        informar("AVISO", "token de Hugging Face", "no hay HF_TOKEN en el entorno ni en un .env de la carpeta actual "
                                                   "(copiar .env.example a .env y completarlo)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica el entorno de la Etapa 2.")
    parser.add_argument("--wav", type=Path, help="un WAV real para probar la decodificación")
    parser.add_argument("--gpu", action="store_true", help="exigir CUDA (para las máquinas con GPU)")
    args = parser.parse_args(argv)
    if args.wav and not args.wav.is_file():
        parser.error(f"no existe {args.wav}")

    print(f"Verificación del entorno de la Etapa 2 · {platform.system()} {platform.release()}\n")
    verificar_python()
    verificar_versiones()
    verificar_importaciones()
    verificar_dispositivo(args.gpu)
    verificar_ffmpeg()
    verificar_decodificacion(args.wav)
    verificar_token()
    fallas = sum(1 for estado, _, _ in _resultados if estado == "FALLA")
    avisos = sum(1 for estado, _, _ in _resultados if estado == "AVISO")
    print(f"\n{'ENTORNO LISTO' if not fallas else 'HAY PROBLEMAS'}: {fallas} fallas, {avisos} avisos")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
