"""Paso 2 de la API de la Etapa 4 (D7): valida y escribe los resultados, y registra los errores.

`transcription.json`, `transcription.meta.json` y, si hubo etiquetado, `speakers.json` se escriben primero en
`.tmp` y se publican con respaldo y reversión (`escribir_juntos`): ante un fallo, el resultado anterior queda intacto
y sin restos.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from asociacion import UMBRALES, Asociacion
from contrato import validar_speakers, validar_transcripcion
from errores import AsociacionError
from fragmentos import semilla

VERSION = "0.3.1"
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


_reemplazar = os.replace  # las pruebas los reemplazan para simular un fallo a mitad de la publicación


def _borrar(ruta: Path) -> None:
    ruta.unlink()


def _escribir_sincronizado(ruta: Path, contenido: bytes) -> Path:
    with open(ruta, "wb") as f:
        f.write(contenido)
        f.flush()
        os.fsync(f.fileno())
    return ruta


def _revertir(hechos: list[Path], respaldos: dict[Path, Path]) -> list[str]:
    """Deshace lo publicado, del último al primero: restaura el respaldo o, si no había, borra lo publicado.
    Devuelve las notas de lo que no se pudo restaurar (vacía si se restauró todo)."""
    notas = []
    for destino in reversed(hechos):
        try:
            if destino in respaldos:
                _reemplazar(respaldos[destino], destino)
            else:
                destino.unlink(missing_ok=True)
        except OSError as e:
            notas.append(f"no se pudo restaurar {destino.name} ({e.strerror or e}); "
                         f"el respaldo queda en {respaldos[destino].name if destino in respaldos else '(no había)'}")
    return notas


def escribir_juntos(carpeta: Path, archivos: dict[str, bytes], borrar: tuple[str, ...] = ()) -> None:
    """Publica `archivos` y borra `borrar` como una unidad: todo o, ante un fallo, lo anterior byte a byte.

    1. Escribe cada `.tmp` y respalda en `.<marca>.bak` lo vigente que se va a reemplazar o borrar. Si algo falla
       acá, borra lo creado: lo vigente no se tocó.
    2. Publica con `os.replace` y después borra. Si algo falla, revierte (ver `_revertir`); si la reversión no se
       completa, conserva todos los `.bak` para recuperar a mano.
    Mismo criterio que `escribir_par` de la Etapa 2. Límite: si el proceso muere entre dos reemplazos, el resultado
    puede quedar inconsistente; `resultado_vigente` lo detecta por el SHA-256 del meta.
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    marca = uuid.uuid4().hex[:12]  # un respaldo de una reversión fallida nunca se pisa
    a_borrar = [carpeta / n for n in borrar if (carpeta / n).is_file()]
    tmps: dict[Path, Path] = {}
    respaldos: dict[Path, Path] = {}
    try:
        for nombre, contenido in archivos.items():
            tmps[carpeta / nombre] = _escribir_sincronizado(carpeta / f"{nombre}.tmp", contenido)
        for destino in [*tmps, *a_borrar]:
            if destino.is_file():
                respaldos[destino] = _escribir_sincronizado(destino.with_name(f"{destino.name}.{marca}.bak"),
                                                            destino.read_bytes())
    except OSError as e:
        for creado in [*tmps.values(), *respaldos.values()]:
            creado.unlink(missing_ok=True)
        raise AsociacionError("escritura", f"{carpeta}: no se pudo escribir ({e.strerror or e})") from e

    hechos: list[Path] = []
    try:
        for destino, tmp in tmps.items():
            _reemplazar(tmp, destino)
            hechos.append(destino)
        for destino in a_borrar:
            _borrar(destino)
            hechos.append(destino)
    except OSError as e:
        notas = _revertir(hechos, respaldos)
        for tmp in tmps.values():
            tmp.unlink(missing_ok=True)
        if not notas:
            for respaldo in respaldos.values():
                respaldo.unlink(missing_ok=True)
        detalle = f"; {'; '.join(notas)}" if notas else "; se conservó el resultado anterior"
        raise AsociacionError("escritura", f"{carpeta}: no se pudo publicar ({e.strerror or e}){detalle}") from e
    for respaldo in respaldos.values():
        respaldo.unlink(missing_ok=True)


def resultado_vigente(carpeta: Path) -> bool:
    """Hay un resultado anterior válido si el SHA-256 de transcription.json coincide con el de su meta."""
    try:
        meta = json.loads((carpeta / META).read_bytes())
        return meta["sha256"][TRANSCRIPCION] == hashlib.sha256((carpeta / TRANSCRIPCION).read_bytes()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError):
        return False


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
    escribir_juntos(carpeta, {**archivos, META: serializar(meta)},
                    borrar=(SPEAKERS,) if etiquetado is None else ())
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
        "resultado_anterior": resultado_vigente(carpeta),
    }
    try:
        escribir_juntos(carpeta, {ERROR: serializar(datos)})
    except AsociacionError:
        return None
    return carpeta / ERROR
