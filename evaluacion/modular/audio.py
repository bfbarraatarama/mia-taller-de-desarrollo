"""Audio de la muestra (requisito «Audio normalizado»).

Cada elemento queda como una carpeta de reunión hecha con `ingestar` del pipeline, la misma normalización
que usa la aplicación: `audio.wav` de 16 kHz, mono y PCM16, más `ingesta.json`. Los miembros se leen de los
originales comprimidos sin extraerlos a disco.
"""

from __future__ import annotations

import hashlib
import io
import subprocess
import tarfile
import tempfile
import wave
import zipfile
from pathlib import Path

import numpy as np

from src.ingesta.audio import ingestar
from src.rar7z import localizar_7zip

FS = 16000
TOLERANCIA_CUADROS = 1  # canales separados de Figshare: se admite 1 cuadro de diferencia (criterio de la Etapa 2)
NORMALIZACION = "ingestar del pipeline: FFmpeg a WAV de 16 kHz, mono y PCM16"


class AudioInvalido(Exception):
    """Un miembro falta en su original o su audio no se puede usar."""


def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def leer_miembro(original: Path, entrada: str) -> bytes:
    """Bytes de `entrada` dentro de un .zip, .tar.gz o .rar, sin extraer el archivo."""
    original = Path(original)
    try:
        if original.suffix == ".zip":
            with zipfile.ZipFile(original) as z:
                return z.read(entrada)
        if original.name.endswith(".tar.gz"):
            with tarfile.open(original, "r:gz") as t:
                return t.extractfile(t.getmember(entrada)).read()
    except KeyError:
        raise AudioInvalido(f"{entrada}: no está en {original.name}") from None
    if original.suffix == ".rar":
        r = subprocess.run([str(localizar_7zip()), "e", "-so", str(original), entrada], capture_output=True)
        if r.returncode != 0 or not r.stdout:
            raise AudioInvalido(f"{entrada}: no está en {original.name} o 7-Zip no pudo leerlo")
        return r.stdout
    raise AudioInvalido(f"{original.name}: formato de original no admitido")


def _ingestar_bytes(datos: bytes, nombre: str, carpeta: Path) -> str:
    """Ingesta `datos` como única fuente de la reunión `carpeta`; devuelve el SHA-256 de su audio.wav."""
    with tempfile.TemporaryDirectory() as tmp:
        fuente = Path(tmp) / nombre
        fuente.write_bytes(datos)
        ingestar([fuente], carpeta)
    return _sha256((Path(carpeta) / "audio.wav").read_bytes())


def preparar_clip(original: Path, entrada: str, carpeta: Path) -> dict:
    """Clip de OpenSLR (WAV 48 kHz en .zip) o de Common Voice (MP3 en .tar.gz) como carpeta de reunión."""
    datos = leer_miembro(original, entrada)
    sha = _ingestar_bytes(datos, Path(entrada).name, Path(carpeta))
    return {"original": Path(original).name, "entrada": entrada, "original_sha256": _sha256(datos),
            "transformacion": f"{NORMALIZACION} (16 kHz)", "sha256": sha}


def _canal(datos: bytes, entrada: str) -> np.ndarray:
    with wave.open(io.BytesIO(datos), "rb") as w:
        forma = (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getcomptype())
        if forma != (FS, 1, 2, "NONE"):
            raise AudioInvalido(f"{entrada}: {forma[0]} Hz, {forma[1]} canales, {forma[2] * 8} bits "
                                f"(se espera PCM16 mono a {FS} Hz)")
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")


def preparar_tarea_figshare(original: Path, canal1: str, canal2: str, carpeta: Path) -> dict:
    """Tarea de Figshare: mezcla mono (L + R) // 2 de sus dos canales, como la evaluación de la Etapa 2 (D16)."""
    crudos = [leer_miembro(original, e) for e in (canal1, canal2)]
    a, b = (_canal(d, e) for d, e in zip(crudos, (canal1, canal2)))
    if abs(len(a) - len(b)) > TOLERANCIA_CUADROS:
        raise AudioInvalido(f"{canal1} y {canal2}: {len(a)} y {len(b)} cuadros (se admite "
                            f"{TOLERANCIA_CUADROS} de diferencia)")
    n = min(len(a), len(b))
    mezcla = ((a[:n].astype(np.int32) + b[:n].astype(np.int32)) // 2).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(mezcla.tobytes())
    sha = _ingestar_bytes(buffer.getvalue(), Path(canal1).name.replace(".channel1", ""), Path(carpeta))
    return {"original": Path(original).name, "entradas": [canal1, canal2],
            "originales_sha256": [_sha256(d) for d in crudos], "cuadros": n,
            "transformacion": f"mezcla mono (L + R) // 2 de los dos canales; {NORMALIZACION}", "sha256": sha}
