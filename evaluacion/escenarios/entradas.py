"""Entradas fijadas de los escenarios de §2.1 (issue #15, requisito «Entradas fijadas»)."""

from __future__ import annotations

import hashlib
import io
import json
import wave
from pathlib import Path

import numpy as np


class EntradaAlterada(Exception):
    """Una entrada no coincide con su SHA-256 del manifiesto."""


def _sha(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def agregar_ruido(wav: bytes, snr_db: float, semilla: int) -> bytes:
    """Suma ruido rosa (espectro 1/f) con semilla fija, escalado a `snr_db` respecto de la potencia de la señal.

    Entrada y salida: WAV PCM16 mono; el resultado se redondea y se recorta al rango de 16 bits."""
    with wave.open(io.BytesIO(wav), "rb") as w:
        fs, canales, ancho = w.getframerate(), w.getnchannels(), w.getsampwidth()
        if (canales, ancho) != (1, 2):
            raise ValueError("se espera un WAV PCM16 mono")
        senal = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)
    rng = np.random.default_rng(semilla)
    n = len(senal)
    espectro = rng.standard_normal(n // 2 + 1) + 1j * rng.standard_normal(n // 2 + 1)
    f = np.fft.rfftfreq(n, 1 / fs)
    escala = np.zeros_like(f)
    escala[1:] = 1 / np.sqrt(f[1:])  # potencia 1/f: ruido rosa; sin componente continua
    ruido = np.fft.irfft(espectro * escala, n)
    potencia_senal = np.mean(senal ** 2)
    ruido *= np.sqrt(potencia_senal / (10 ** (snr_db / 10)) / np.mean(ruido ** 2))
    mezcla = np.clip(np.round(senal + ruido), -32768, 32767).astype("<i2")
    salida = io.BytesIO()
    with wave.open(salida, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(mezcla.tobytes())
    return salida.getvalue()


def construir_manifiesto(escenarios: dict[str, dict], raiz: Path) -> dict:
    """{escenario: {"fuentes": [rutas en orden], "transformacion": texto opcional}} → manifiesto con SHA-256."""
    raiz = Path(raiz)
    salida = {}
    for nombre, e in sorted(escenarios.items()):
        salida[nombre] = {"fuentes": [{"ruta": Path(f).resolve().relative_to(raiz.resolve()).as_posix(),
                                       "sha256": _sha(Path(f).read_bytes())} for f in e["fuentes"]],
                          **({"transformacion": e["transformacion"]} if e.get("transformacion") else {})}
    return {"version": 1, "escenarios": salida}


def verificar_entradas(manifiesto: Path, raiz: Path, *, estricto: bool = False) -> list[str]:
    """Problemas de las entradas contra el manifiesto; con `estricto`, lanza EntradaAlterada si hay alguno."""
    datos = json.loads(Path(manifiesto).read_text(encoding="utf-8"))
    problemas = []
    for nombre, e in datos["escenarios"].items():
        for f in e["fuentes"]:
            ruta = Path(raiz) / f["ruta"]
            if not ruta.is_file():
                problemas.append(f"{nombre}: falta {f['ruta']}")
            elif (encontrado := _sha(ruta.read_bytes())) != f["sha256"]:
                problemas.append(f"{nombre}: {f['ruta']} SHA-256 esperado {f['sha256']}, encontrado {encontrado}")
    if problemas and estricto:
        raise EntradaAlterada("Entradas que no coinciden con el manifiesto:\n" + "\n".join(f"- {p}" for p in problemas))
    return problemas
