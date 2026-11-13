"""Validador del contrato de `diarization.json` (solo biblioteca estándar).

Lo pueden usar el script de contratos de 2.3 y la Etapa 4 desde el entorno de la interfaz, sin PyTorch.

Uso:
    python contrato.py diarization.json AUDIO.wav [--meta diarization.meta.json]

Termina con código 0 si no hay violaciones y 1 si las hay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

CLAVES_RAIZ = {"segments"}
CLAVES_SEGMENTO = {"start", "end", "speaker"}


def _es_numero(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def validar_diarizacion(datos, duracion: float) -> list[str]:
    """Devuelve todas las violaciones del contrato, cada una con su ubicación. Lista vacía = válido."""
    if not isinstance(datos, dict):
        return ["raíz: no es un objeto JSON"]
    violaciones = []
    for clave in sorted(set(datos) - CLAVES_RAIZ):
        violaciones.append(f"raíz: campo no permitido '{clave}'")
    if "segments" not in datos:
        violaciones.append("raíz: falta 'segments'")
        return violaciones
    segmentos = datos["segments"]
    if not isinstance(segmentos, list):
        violaciones.append("raíz: 'segments' no es una lista")
        return violaciones

    inicio_previo = None
    for i, seg in enumerate(segmentos):
        lugar = f"segments[{i}]"
        if not isinstance(seg, dict):
            violaciones.append(f"{lugar}: no es un objeto")
            continue
        for clave in sorted(set(seg) - CLAVES_SEGMENTO):
            violaciones.append(f"{lugar}: campo no permitido '{clave}'")
        for clave in sorted(CLAVES_SEGMENTO - set(seg)):
            violaciones.append(f"{lugar}: falta '{clave}'")
        inicio, fin = seg.get("start"), seg.get("end")
        for nombre, valor in (("start", inicio), ("end", fin)):
            if nombre in seg and not _es_numero(valor):
                violaciones.append(f"{lugar}: '{nombre}' no es un número finito ({valor!r})")
        if "speaker" in seg and not (isinstance(seg["speaker"], str) and seg["speaker"].strip()):
            violaciones.append(f"{lugar}: 'speaker' vacío o no es texto ({seg['speaker']!r})")
        if _es_numero(inicio) and _es_numero(fin):
            if inicio < 0:
                violaciones.append(f"{lugar}: start={inicio} es negativo")
            if not inicio < fin:
                violaciones.append(f"{lugar}: start={inicio} no es menor que end={fin}")
            if fin > duracion:
                violaciones.append(f"{lugar}: end={fin} supera la duración del audio ({duracion} s)")
        if _es_numero(inicio):
            if inicio_previo is not None and inicio < inicio_previo:
                violaciones.append(f"{lugar}: start={inicio} rompe el orden por start (anterior {inicio_previo})")
            inicio_previo = inicio
    return violaciones


def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def validar_par(json_path, meta_path) -> list[str]:
    """Comprueba que `diarization.json` y `diarization.meta.json` son de la misma ejecución exitosa."""
    json_path, meta_path = Path(json_path), Path(meta_path)
    violaciones = []
    for ruta in (json_path, meta_path):
        if not ruta.is_file():
            violaciones.append(f"par: no existe {ruta}")
    if violaciones:
        return violaciones
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        datos = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"par: no se pudo leer ({type(e).__name__}: {e})"]
    esperado = meta.get("diarization_sha256") if isinstance(meta, dict) else None
    if not esperado:
        return ["par: el meta no tiene 'diarization_sha256'"]
    if sha256_archivo(json_path) != esperado:
        violaciones.append("par: el SHA-256 de diarization.json no coincide con el del meta "
                           "(no corresponden a la misma ejecución)")
    segmentos = datos.get("segments") if isinstance(datos, dict) else None
    if isinstance(segmentos, list):
        if meta.get("segmentos") != len(segmentos):
            violaciones.append(f"par: el meta declara {meta.get('segmentos')} segmentos y el JSON tiene "
                               f"{len(segmentos)}")
        etiquetas = {s.get("speaker") for s in segmentos if isinstance(s, dict)}
        if meta.get("hablantes") != len(etiquetas):
            violaciones.append(f"par: el meta declara {meta.get('hablantes')} hablantes y el JSON tiene "
                               f"{len(etiquetas)}")
    return violaciones


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida diarization.json contra el contrato de la Etapa 2.")
    parser.add_argument("diarizacion", type=Path, help="diarization.json")
    parser.add_argument("audio", type=Path, help="WAV de entrada (se usa su duración)")
    parser.add_argument("--meta", type=Path, help="diarization.meta.json: comprueba además el par")
    args = parser.parse_args(argv)

    from entrada import validar_audio  # solo biblioteca estándar
    from errores import DiarizacionError

    try:
        duracion = validar_audio(args.audio)
    except DiarizacionError as e:
        print(f"audio: {e.mensaje}", file=sys.stderr)
        return 1
    try:
        datos = json.loads(args.diarizacion.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"diarización: no se pudo leer ({type(e).__name__}: {e})", file=sys.stderr)
        return 1
    violaciones = validar_diarizacion(datos, duracion)
    if args.meta:
        violaciones += validar_par(args.diarizacion, args.meta)
    for v in violaciones:
        print(v)
    print(f"{len(violaciones)} violaciones" if violaciones else "0 violaciones: dentro del contrato")
    return 1 if violaciones else 0


if __name__ == "__main__":
    sys.exit(main())
