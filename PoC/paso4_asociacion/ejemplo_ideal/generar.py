"""Ejemplo ideal (D10 de design.md): entradas perfectas para probar la Etapa 4 sin las Etapas 2 y 3.

Sintetiza cada intervención de `guion.json` con espeak-ng, las concatena con silencio entre ellas y escribe:
  audio.wav         16 kHz, mono, PCM16
  diarization.json  un turno por intervención, con los tiempos de la concatenación
  asr.json          un segmento por intervención; tiempos de palabra en proporción a sus letras
  referencia.json   hablante y nombre esperados por palabra, y con qué se generó

Una intervención con `"encima_de_anterior": s` no se concatena: se mezcla sobre la intervención anterior, s
segundos después de que esta empieza (habla superpuesta). `guion_manual.json` la usa para la lista de chequeo
manual (tarea 10.1): 8 hablantes, uno de los cuales solo interrumpe y nunca habla solo.

Uso (desde PoC/paso4_asociacion/):
    python ejemplo_ideal/generar.py [--guion GUION] [--salida CARPETA]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

DIRECTORIO = Path(__file__).resolve().parent
GUION = DIRECTORIO / "guion.json"
GUION_MANUAL = DIRECTORIO / "guion_manual.json"
SALIDA = DIRECTORIO / "generado"

FS = 16000
SILENCIO_BORDES_S = 0.5
SILENCIO_ENTRE_S = 0.6
# espeak-ng deja silencio al principio y al final de cada frase; se recorta para que el turno sea solo voz.
UMBRAL_VOZ = 10 ** (-40 / 20)  # -40 dBFS


def version_espeak() -> str:
    salida = subprocess.run(["espeak-ng", "--version"], check=True, capture_output=True, text=True).stdout
    m = re.search(r"\d+\.\d+(\.\d+)?", salida)
    return m.group(0) if m else salida.strip()


def sintetizar(texto: str, voz: str, velocidad: int) -> np.ndarray:
    """Devuelve la voz a 16 kHz, sin el silencio de los extremos."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "frase.wav"
        subprocess.run(["espeak-ng", "-v", voz, "-s", str(velocidad), "-w", str(ruta), texto],
                       check=True, capture_output=True)
        x, fs = sf.read(ruta, dtype="float64")
    g = gcd(FS, fs)
    x = resample_poly(x, FS // g, fs // g)
    con_voz = np.flatnonzero(np.abs(x) > UMBRAL_VOZ)
    if con_voz.size == 0:
        raise RuntimeError(f"espeak-ng no produjo voz para: {texto!r}")
    return x[con_voz[0]:con_voz[-1] + 1]


def repartir_palabras(texto: str, inicio: float, fin: float) -> list[dict]:
    """Tiempos por palabra en proporción a sus letras; la primera empieza en `inicio` y la última termina en `fin`."""
    palabras = texto.split()
    pesos = [max(1, sum(c.isalnum() for c in p)) for p in palabras]
    total, acumulado, bordes = sum(pesos), 0, [inicio]
    for peso in pesos[:-1]:
        acumulado += peso
        bordes.append(round(inicio + (fin - inicio) * acumulado / total, 3))
    bordes.append(fin)
    return [{"word": p, "start": bordes[i], "end": bordes[i + 1]} for i, p in enumerate(palabras)]


def escribir_json(ruta: Path, datos) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generar(salida: str | Path = SALIDA, guion: str | Path = GUION) -> Path:
    salida, guion = Path(salida), Path(guion)
    datos = json.loads(guion.read_text(encoding="utf-8"))
    velocidad = datos["velocidad_palabras_por_minuto"]

    etiquetas: dict[str, str] = {}  # nombre -> SPEAKER_NN, en orden de aparición
    for interv in datos["intervenciones"]:
        etiquetas.setdefault(interv["hablante"], f"SPEAKER_{len(etiquetas):02d}")

    bordes, entre = round(SILENCIO_BORDES_S * FS), round(SILENCIO_ENTRE_S * FS)
    pistas, turnos, segmentos, palabras_ref = [], [], [], []
    cursor = bordes            # fin de la última intervención concatenada, en muestras
    inicio_anterior = None     # inicio de la última intervención concatenada
    for i, interv in enumerate(datos["intervenciones"]):
        voz = sintetizar(interv["texto"], datos["voces"][interv["hablante"]], velocidad)
        encima = interv.get("encima_de_anterior")
        if encima is None:
            muestra = cursor + (entre if i else 0)
            inicio_anterior = muestra
        else:
            muestra = inicio_anterior + round(encima * FS)
        cursor = max(cursor, muestra + voz.size)
        pistas.append((muestra, voz))
        inicio, fin = round(muestra / FS, 3), round((muestra + voz.size) / FS, 3)

        etiqueta = etiquetas[interv["hablante"]]
        palabras = repartir_palabras(interv["texto"], inicio, fin)
        turnos.append({"start": inicio, "end": fin, "speaker": etiqueta})
        segmentos.append({"start": inicio, "end": fin, "text": interv["texto"], "words": palabras})
        palabras_ref += [{**p, "speaker": etiqueta, "name": interv["hablante"]} for p in palabras]
    # Los contratos piden turnos ordenados por inicio; una intervención superpuesta puede empezar antes que otra
    for lista in (turnos, segmentos, palabras_ref):
        lista.sort(key=lambda x: x["start"])

    audio = np.zeros(cursor + bordes)
    for muestra, voz in pistas:
        audio[muestra:muestra + voz.size] += voz

    salida.mkdir(parents=True, exist_ok=True)
    sf.write(salida / "audio.wav", np.clip(audio, -1.0, 1.0), FS, subtype="PCM_16")
    escribir_json(salida / "diarization.json", {"segments": turnos})
    escribir_json(salida / "asr.json", {"language": "es", "segments": segmentos})
    escribir_json(salida / "referencia.json", {
        "generado_con": {"espeak_ng": version_espeak(),
                         "guion_sha256": hashlib.sha256(guion.read_bytes()).hexdigest()},
        "hablantes": {etiqueta: nombre for nombre, etiqueta in etiquetas.items()},
        "palabras": palabras_ref,
    })
    return salida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera el ejemplo ideal de la Etapa 4 (D10).")
    parser.add_argument("--guion", type=Path, default=GUION, help=f"guion (por defecto {GUION.name})")
    parser.add_argument("--salida", type=Path, default=SALIDA, help=f"carpeta de salida (por defecto {SALIDA})")
    args = parser.parse_args(argv)
    carpeta = generar(args.salida, args.guion)
    duracion = sf.info(carpeta / "audio.wav").duration
    turnos = json.loads((carpeta / "diarization.json").read_text(encoding="utf-8"))["segments"]
    print(f"{carpeta} · {duracion:.1f} s · {len(turnos)} turnos")
    for t in turnos:
        print(f"  {t['speaker']}  {t['start']:7.3f} – {t['end']:7.3f}  ({t['end'] - t['start']:5.2f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
