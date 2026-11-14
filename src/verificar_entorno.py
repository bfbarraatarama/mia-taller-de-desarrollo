"""Verificación del entorno general del repositorio, sin descargas de modelos ni datos.

Uso: python -m src.verificar_entorno [--gpu] [--wav audio.wav].
En Linux con captura automática, ejecutar con pw-jack.
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
import tomllib
import warnings
import wave
from importlib import metadata
from pathlib import Path

from .rutas import DIRECTORIO_PROYECTO

RESTRICCIONES = DIRECTORIO_PROYECTO / "constraints.txt"
PYTHON_ESPERADO = (3, 12)
NO_FIJADOS = re.compile(r"^(pip|setuptools|wheel|mia104-poc|nvidia-.*|triton)$")


def requisitos_directos():
    from packaging.requirements import Requirement
    proyecto = tomllib.loads((DIRECTORIO_PROYECTO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requisitos = proyecto["dependencies"] + proyecto["optional-dependencies"]["test"]
    parsed = [Requirement(texto) for texto in requisitos]
    return [r for r in parsed if r.marker is None or r.marker.evaluate()]


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
        nombre = normalizar_nombre(m[1])
        if nombre in restricciones:
            raise ValueError(f"Restricción duplicada: {nombre}")
        restricciones[nombre] = m[2].replace(" ", "")
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
    try:
        restricciones = leer_restricciones()
        directas = {normalizar_nombre(r.name): r for r in requisitos_directos()}
    except (OSError, ValueError, ImportError) as e:
        informar("FALLA", "definición del entorno", f"{type(e).__name__}: {e}")
        return
    instalados = {normalizar_nombre(d.metadata["Name"]): d.version for d in metadata.distributions()}
    faltan = sorted(set(directas) - set(instalados))
    sin_restriccion = sorted(set(directas) - set(restricciones))
    distintos = [f"{n} {v} (se espera {restricciones[n]})"
                 for n, v in sorted(instalados.items()) if n in restricciones and not cumple(v, restricciones[n])]
    for nombre, requisito in sorted(directas.items()):
        version = instalados.get(nombre)
        if version and not requisito.specifier.contains(version, prereleases=True):
            distintos.append(f"{nombre} {version} no cumple {requisito.specifier}")
    for tema, problemas in (("dependencias directas faltantes", faltan),
                            ("dependencias directas sin restricciones", sin_restriccion),
                            ("versiones incompatibles", distintos)):
        if problemas:
            informar("FALLA", tema, "; ".join(problemas))
    if not (faltan or sin_restriccion or distintos):
        informar("OK", "versiones", f"{len(directas)} directas, {len(restricciones)} restricciones compatibles")
    sobrantes = sorted(n for n in instalados if n not in restricciones and not NO_FIJADOS.match(n))
    if sobrantes:
        informar("AVISO", "paquetes fuera de restricciones", ", ".join(sobrantes))
    verificar_comando(sys.executable, ("-m", "pip", "check"), tema="pip check")


def verificar_importaciones() -> None:
    for modulo in ("torch", "torchaudio", "torchcodec", "pyannote.audio", "pyannote.metrics", "dotenv",
                   "numpy", "pandas", "scipy", "sounddevice", "soundfile", "PySide6.QtWidgets", "whisper",
                   "pydantic", "ollama", "boto3", "botocore", "httpx", "pyarrow.parquet", "matplotlib",
                   "lxml.etree", "huggingface_hub", "datacollective", "jupyter_core", "nbconvert", "ipykernel",
                   "IPython", "pytest"):
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
    except Exception:
        return  # La importación de torch ya se comprueba por separado.
    variante = torch.__version__.partition("+")[2] or "sin etiqueta"
    try:
        audio = metadata.version("torchaudio").partition("+")[2]
    except metadata.PackageNotFoundError:
        audio = ""
    if variante not in {"cpu", "cu128"} or variante != audio:
        informar("FALLA", "variante PyTorch", "usar un perfil CPU o cu128; torch y torchaudio deben coincidir")
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


def verificar_comando(ejecutable: str, argumentos: tuple[str, ...], *, tema: str | None = None) -> bool:
    tema = tema or ejecutable
    ruta = shutil.which(ejecutable)
    if not ruta:
        informar("FALLA", tema, "ejecutable no encontrado")
        return False
    try:
        r = subprocess.run([ruta, *argumentos], capture_output=True, text=True, errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        informar("FALLA", tema, type(e).__name__)
        return False
    if r.returncode == 0:
        detalle = (r.stdout.strip() or r.stderr.strip() or ruta).splitlines()[0]
    else:
        detalle = f"código {r.returncode}: " + (r.stderr.strip() or r.stdout.strip() or ruta)
    informar("OK" if r.returncode == 0 else "FALLA", tema, detalle[:1000])
    return r.returncode == 0


def verificar_sistema() -> None:
    verificar_comando("ffprobe", ("-version",))
    verificar_comando("espeak-ng", ("--version",))
    from PoC.paso2_diarizacion.evaluacion.rar7z import ErrorVerificacion, localizar_7zip
    try:
        siete = localizar_7zip()
        r = subprocess.run([str(siete), "i"], capture_output=True, text=True, errors="replace", timeout=20)
        if r.returncode != 0 or not re.search(r"\bRar5?\b", r.stdout, re.I):
            informar("FALLA", "7-Zip", "no se pudo confirmar soporte RAR")
        else:
            informar("OK", "7-Zip", f"{siete}; soporte RAR disponible")
    except (ErrorVerificacion, OSError, subprocess.SubprocessError):
        informar("FALLA", "7-Zip", "no disponible; revisar PATH o SIETE_ZIP")
    from .bibliotecas import cargar_libarchive
    try:
        biblioteca = cargar_libarchive()
        informar("OK", "libarchive", str(biblioteca._name))
    except OSError:
        informar("FALLA", "libarchive", "biblioteca no disponible para el Hito 2")
    try:
        import sounddevice as sd
        informar("OK", "PortAudio", sd.get_portaudio_version()[1])
    except Exception:
        informar("FALLA", "PortAudio", "no se pudo cargar mediante sounddevice")
    if platform.system() == "Linux":
        for comando in ("pactl", "pw-link", "pw-jack"):
            if not shutil.which(comando):
                informar("FALLA", comando, "necesario para la captura automática Linux")
            else:
                informar("OK", comando, "disponible")
        try:
            import sounddevice as sd
            jack = any("JACK" in api["name"] for api in sd.query_hostapis())
        except Exception:
            jack = False
        informar("OK" if jack else "AVISO", "JACK", "disponible" if jack else "ejecutar con pw-jack en una sesión PipeWire activa")
        if jack and shutil.which("pactl") and shutil.which("pw-link"):
            verificar_comando("pactl", ("info",), tema="servidor de audio")
            verificar_comando("pw-link", ("-i",), tema="puertos PipeWire")
    else:
        informar("AVISO", "captura", "en esta plataforma se requieren fuentes manuales de micrófono y loopback")
    disponible = shutil.which("ollama") is not None
    informar("OK" if disponible else "FALLA", "Ollama",
             "CLI disponible (modelo y servicio no consultados)" if disponible else "instalar Ollama para generar minutas locales")


def verificar_qt() -> None:
    if platform.system() == "Linux" and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        informar("AVISO", "Qt", "sin sesión gráfica; plataforma de Qt no comprobada")
        return
    verificar_comando(sys.executable, ("-c", "from PySide6.QtWidgets import QApplication; app = QApplication([]); print(app.platformName())"), tema="plataforma Qt")


def verificar_ffmpeg() -> None:
    verificar_comando("ffmpeg", ("-version",))
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
                informar("FALLA", f"decodificación ({nombre})", f"{type(e).__name__}: {(str(e).splitlines() or [''])[0][:200]}")
                continue
            completo = n == cuadros and muestras.sample_rate == hz
            formato = "" if (hz, canales) == (16000, 1) else f" — AVISO: {hz} Hz, {canales} canales (la Etapa 2 exige 16 kHz mono)"
            informar("OK" if completo else "FALLA", f"decodificación ({nombre})",
                     f"torchcodec leyó {n} muestras a {muestras.sample_rate} Hz; la cabecera declara {cuadros}{formato}")


def verificar_token() -> None:
    from .diarizacion.entrada import obtener_token
    if obtener_token():
        informar("OK", "token de Hugging Face", "configurado (no se muestra)")
    else:
        informar("AVISO", "token de Hugging Face", "no hay HF_TOKEN en el entorno ni en un .env de la carpeta actual "
                                                   "(copiar .env.example a .env y completarlo)")


def main(argv: list[str] | None = None) -> int:
    _resultados.clear()
    parser = argparse.ArgumentParser(description="Verifica el entorno general del repositorio.")
    parser.add_argument("--wav", type=Path, help="un WAV real para probar la decodificación")
    parser.add_argument("--gpu", action="store_true", help="exigir CUDA (para las máquinas con GPU)")
    args = parser.parse_args(argv)
    if args.wav and not args.wav.is_file():
        parser.error(f"no existe {args.wav}")

    print(f"Verificación del entorno del repositorio · {platform.system()} {platform.release()}\n")
    verificar_python()
    verificar_versiones()
    verificar_importaciones()
    verificar_dispositivo(args.gpu)
    verificar_ffmpeg()
    verificar_sistema()
    verificar_qt()
    verificar_decodificacion(args.wav)
    verificar_token()
    fallas = sum(1 for estado, _, _ in _resultados if estado == "FALLA")
    avisos = sum(1 for estado, _, _ in _resultados if estado == "AVISO")
    print(f"\n{'ENTORNO LISTO' if not fallas else 'HAY PROBLEMAS'}: {fallas} fallas, {avisos} avisos")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())