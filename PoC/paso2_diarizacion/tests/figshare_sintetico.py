"""Generador de una caché de Figshare sintética (S26) para las pruebas de las tareas 6.3 a 6.7.

Arma en `base/cache`: `extraidos/` con el WAV estéreo completo, las dos anotaciones y los dos WAV separados de cada
tarea, y `wavs.rar` / `phrases.rar` (en formato 7z, que 7-Zip lista igual) con esos mismos archivos.
"""

import hashlib
import subprocess
import wave

import numpy as np

from evaluacion.preparar_figshare import ruta_separado, rutas_tarea

FS = 16000
CH1 = "0.0\t1.0\t#\n1.0\t2.5\thola\n2.5\t3.0\t#\n"
CH2 = "0.0\t0.8\tbuen día\n0.8\t2.0\t#\n2.0\t3.004\tsí\n"   # el último fin excede 0,004 s: se ajusta


def escribir_wav(ruta, muestras: np.ndarray, fs=FS):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    muestras = muestras if muestras.ndim == 2 else muestras[:, None]
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(muestras.shape[1])
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(np.clip(muestras, -32768, 32767).astype("<i2").tobytes())


def armar(base, siete_zip, anotaciones=None, segundos=3.0, semilla=7):
    """anotaciones: {tarea: (texto channel1, texto channel2)}; por defecto solo la tarea 04 con CH1 y CH2."""
    anotaciones = anotaciones or {"04": (CH1, CH2)}
    cache = base / "cache"
    extraidos = cache / "extraidos"
    n = int(segundos * FS)
    for i, (tarea, (ch1, ch2)) in enumerate(sorted(anotaciones.items())):
        rng = np.random.default_rng(semilla + i)
        izq, der = rng.normal(0, 3000, n).astype(np.int32), rng.normal(0, 3000, n).astype(np.int32)
        rutas = rutas_tarea(tarea)
        escribir_wav(extraidos / rutas["wav_completo"], np.stack([izq, der], axis=1))
        for clave, texto in (("channel1", ch1), ("channel2", ch2)):
            (extraidos / rutas[clave]).parent.mkdir(parents=True, exist_ok=True)
            (extraidos / rutas[clave]).write_bytes(texto.encode("utf-8"))
        ruido = rng.integers(-30, 30, n)
        for c, sep in ((1, izq), (2, der)):
            escribir_wav(extraidos / ruta_separado(tarea, c), sep + ruido)
    for rar, carpeta in (("wavs.rar", "wavs"), ("phrases.rar", "phrases")):
        r = subprocess.run([siete_zip, "a", "-t7z", "-bso0", "-bsp0", str(cache / rar), carpeta],
                           cwd=extraidos, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    registro = {}
    for nombre in ("phrases.rar", "wavs.rar"):
        d = (cache / nombre).read_bytes()
        registro[nombre] = {"bytes": len(d), "md5": hashlib.md5(d).hexdigest(), "sha256": hashlib.sha256(d).hexdigest()}
    return cache, extraidos, registro


def huellas(carpeta) -> dict:
    return {p.relative_to(carpeta).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(carpeta.rglob("*")) if p.is_file()}
