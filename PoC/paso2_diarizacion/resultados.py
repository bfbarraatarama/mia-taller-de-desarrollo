"""Carpeta de resultados de cada reunión, escritura del par y registro de errores (design.md §5).

- `diarization.json` y `diarization.meta.json` solo se escriben en un éxito, vía `.tmp` + `os.replace`.
- Un fallo escribe `diarization.error.json` y nunca toca el par anterior.
- Un éxito borra el `diarization.error.json` de un intento anterior.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

NOMBRE_JSON = "diarization.json"
NOMBRE_META = "diarization.meta.json"
NOMBRE_ERROR = "diarization.error.json"


def carpeta_reunion(audio, salida=None) -> Path:
    """Por defecto `<carpeta del audio>/<nombre del audio sin extensión>/`; o la carpeta indicada."""
    audio = Path(audio)
    return Path(salida) if salida is not None else audio.parent / audio.stem


def serializar(datos) -> bytes:
    return (json.dumps(datos, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _escribir_tmp(destino: Path, contenido: bytes) -> Path:
    tmp = destino.with_name(destino.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(contenido)
        f.flush()
        os.fsync(f.fileno())
    return tmp


def escribir_par(carpeta, diarizacion: dict, meta: dict) -> dict:
    """Escribe el par de una ejecución exitosa y devuelve el meta escrito (con `diarization_sha256`)."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    contenido = serializar(diarizacion)
    meta = dict(meta, diarization_sha256=hashlib.sha256(contenido).hexdigest())
    tmps = []
    try:
        tmps.append(_escribir_tmp(carpeta / NOMBRE_JSON, contenido))
        tmps.append(_escribir_tmp(carpeta / NOMBRE_META, serializar(meta)))
    except OSError:
        for tmp in tmps:  # si falla antes de reemplazar, el par anterior queda intacto y sin restos
            tmp.unlink(missing_ok=True)
        raise
    os.replace(tmps[0], carpeta / NOMBRE_JSON)
    os.replace(tmps[1], carpeta / NOMBRE_META)
    (carpeta / NOMBRE_ERROR).unlink(missing_ok=True)
    return meta


def run_id_vigente(carpeta) -> str | None:
    """`run_id` del par válido que hay en la carpeta, o None si no hay uno."""
    carpeta = Path(carpeta)
    if not ((carpeta / NOMBRE_JSON).is_file() and (carpeta / NOMBRE_META).is_file()):
        return None
    try:
        return json.loads((carpeta / NOMBRE_META).read_text(encoding="utf-8")).get("run_id")
    except (OSError, ValueError, AttributeError):
        return None


def registrar_error(carpeta, *, run_id: str, inicio: str, etapa: str, tipo: str, mensaje: str,
                    modo_dispositivo: str) -> Path:
    """Escribe `diarization.error.json` sin tocar `diarization.json` ni `diarization.meta.json`."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    anterior = run_id_vigente(carpeta)
    datos = {
        "run_id": run_id,
        "inicio": inicio,
        "etapa": etapa,
        "tipo": tipo,
        "mensaje": mensaje,
        "modo_dispositivo": modo_dispositivo,
        "resultado_anterior_conservado": anterior is not None,
        "run_id_anterior": anterior,
    }
    destino = carpeta / NOMBRE_ERROR
    os.replace(_escribir_tmp(destino, serializar(datos)), destino)
    return destino
