"""Paso 2 de la API de la Etapa 4 (D7): valida y escribe los resultados, y registra los errores.

`transcription.json`, `transcription.meta.json` y, si hubo etiquetado, `speakers.json` se escriben primero en
`.tmp` y se reemplazan con `os.replace` solo si todo salió bien: ante un fallo, el resultado anterior queda intacto y sin restos.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from asociacion import UMBRALES, Asociacion
from contrato import validar_speakers, validar_transcripcion
from errores import AsociacionError
from fragmentos import semilla

VERSION = "0.3.0"
TRANSCRIPCION = "transcription.json"
META = "transcription.meta.json"
SPEAKERS = "speakers.json"
ERROR = "transcription.error.json"

REGLAS = ["D1 máxima superposición", "D2 empates por continuidad", "D3 huecos de hasta 0,25 s",
          "D4 cortes por hablante y segmento de Whisper", "D5 marcas overlap y ambiguous"]


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


def _violacion(archivo: str, violaciones: list[str]) -> AsociacionError:
    return AsociacionError("contrato", f"{archivo} no cumple el contrato ({len(violaciones)} violaciones; "
                                       f"primera: {violaciones[0]})", violaciones=violaciones)


def escribir(asociacion: Asociacion, etiquetado=None, salida: str | Path | None = None) -> Path:
    """Sin etiquetado (`None`, CLI o «Seguir sin nombres»): `name: null` en todas las intervenciones, sin
    `speakers.json`, y se borra el de un etiquetado anterior para que no contradiga a la transcripción.
    Con etiquetado (`etiquetado.Etiquetado`): nombres por etiqueta y `speakers.json` con el fragmento en pantalla.
    """
    carpeta = Path(salida) if salida is not None else asociacion.rutas.salida
    nombres = etiquetado.nombres if etiquetado is not None else {}
    segmentos = []
    for i in asociacion.intervenciones:
        d = i.a_dict()
        d["name"] = nombres.get(i.speaker) if i.speaker is not None else None
        segmentos.append(d)
    datos = {"segments": segmentos}
    violaciones = validar_transcripcion(datos, asociacion.duracion, asociacion.etiquetas)
    if violaciones:
        raise _violacion(TRANSCRIPCION, violaciones)
    archivos = {TRANSCRIPCION: serializar(datos)}

    if etiquetado is not None:
        speakers = {e: {"name": nombres.get(e), "clip_start": etiquetado.clips[e][0],
                        "clip_end": etiquetado.clips[e][1]} for e in asociacion.etiquetas}
        violaciones = validar_speakers(speakers, asociacion.duracion, asociacion.etiquetas)
        if violaciones:
            raise _violacion(SPEAKERS, violaciones)
        archivos[SPEAKERS] = serializar(speakers)

    r = asociacion.rutas
    meta = {
        "version": VERSION,
        "fecha": ahora(),
        "entradas": {"audio": str(r.audio), "diarizacion": str(r.diarizacion), "asr": str(r.asr)},
        "duracion_audio_s": asociacion.duracion,
        "sha256": {**asociacion.sha256, **{n: hashlib.sha256(c).hexdigest() for n, c in archivos.items()}},
        "etiquetado": etiquetado is not None,
        "umbrales": UMBRALES,
        "semilla_fragmentos": semilla(asociacion.sha256["diarization.json"]),
        "reglas": REGLAS,
        "recortes_asr": asociacion.recortes_asr,
        "conteos": asociacion.conteos,
    }
    escribir_juntos(carpeta, {**archivos, META: serializar(meta)})
    if etiquetado is None:
        (carpeta / SPEAKERS).unlink(missing_ok=True)
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
