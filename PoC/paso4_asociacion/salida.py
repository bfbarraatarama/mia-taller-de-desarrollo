"""Paso 2 de la API de la Etapa 4 (D7): valida y escribe los resultados, y registra los errores.

`transcription.json` y `transcription.meta.json` se escriben primero en `.tmp` y se reemplazan con `os.replace`
solo si todo salió bien: ante un fallo, el resultado anterior queda intacto y sin restos.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from asociacion import Asociacion
from contrato import validar_transcripcion
from errores import AsociacionError

VERSION = "0.1.0"
TRANSCRIPCION = "transcription.json"
META = "transcription.meta.json"
ERROR = "transcription.error.json"

IMPLEMENTADO = ["D1 asignación por máxima superposición", "D4 intervenciones por hablante y segmento de Whisper"]
PENDIENTE = ["D2 empates por continuidad (tarea 3.1)", "D3 palabras en huecos (tarea 3.1)",
             "D5 marcas overlap y ambiguous por cobertura (tarea 3.2)"]


def serializar(datos) -> bytes:
    return (json.dumps(datos, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def escribir_juntos(carpeta: Path, archivos: dict[str, bytes]) -> None:
    """Escribe todos en `.tmp` y recién después los reemplaza; si algo falla antes, borra los `.tmp`."""
    carpeta.mkdir(parents=True, exist_ok=True)
    temporales = []
    try:
        for nombre, contenido in archivos.items():
            tmp = carpeta / f"{nombre}.tmp"
            with open(tmp, "wb") as f:
                f.write(contenido)
                f.flush()
                os.fsync(f.fileno())
            temporales.append((tmp, carpeta / nombre))
    except OSError as e:
        for tmp, _ in temporales:
            tmp.unlink(missing_ok=True)
        raise AsociacionError("escritura", f"{carpeta}: no se pudo escribir ({e.strerror or e})") from e
    for tmp, destino in temporales:
        os.replace(tmp, destino)


def escribir(asociacion: Asociacion, salida: str | Path | None = None) -> Path:
    """Sin etiquetado: todas las intervenciones con `name: null` y sin `speakers.json`."""
    carpeta = Path(salida) if salida is not None else asociacion.rutas.salida
    datos = {"segments": [i.a_dict() for i in asociacion.intervenciones]}
    violaciones = validar_transcripcion(datos, asociacion.duracion, asociacion.etiquetas)
    if violaciones:
        raise AsociacionError("contrato", f"transcription.json no cumple el contrato ({len(violaciones)} "
                              f"violaciones; primera: {violaciones[0]})", violaciones=violaciones)
    contenido = serializar(datos)
    r = asociacion.rutas
    meta = {
        "version": VERSION,
        "fecha": ahora(),
        "entradas": {"audio": str(r.audio), "diarizacion": str(r.diarizacion), "asr": str(r.asr)},
        "duracion_audio_s": asociacion.duracion,
        "sha256": {**asociacion.sha256, TRANSCRIPCION: hashlib.sha256(contenido).hexdigest()},
        "etiquetado": False,
        "umbrales": {},
        "implementado": IMPLEMENTADO,
        "pendiente": PENDIENTE,
        "recortes_asr": asociacion.recortes_asr,
        "conteos": asociacion.conteos,
    }
    escribir_juntos(carpeta, {TRANSCRIPCION: contenido, META: serializar(meta)})
    (carpeta / ERROR).unlink(missing_ok=True)
    return carpeta / TRANSCRIPCION


def registrar_error(carpeta: Path, error: AsociacionError) -> Path | None:
    """Escribe `transcription.error.json`. Si tampoco se puede escribir, el fallo igual llega por la excepción."""
    datos = {
        "fecha": ahora(),
        "paso": error.paso,
        "mensaje": error.mensaje,
        "archivo": error.archivo,
        "violaciones": error.violaciones,
        "causa": type(error.__cause__).__name__ if error.__cause__ else None,
        "resultado_anterior": (carpeta / TRANSCRIPCION).is_file(),
    }
    try:
        escribir_juntos(carpeta, {ERROR: serializar(datos)})
    except AsociacionError:
        return None
    return carpeta / ERROR
