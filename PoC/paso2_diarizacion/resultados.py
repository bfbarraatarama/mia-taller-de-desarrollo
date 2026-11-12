"""Carpeta de resultados de cada reunión, escritura del par y registro de errores (design.md §5).

- `diarization.json` y `diarization.meta.json` solo se escriben en un éxito, vía `.tmp` + `os.replace`.
- Publicación con respaldo y reversión: si falla cualquiera de los dos `os.replace`, se restaura el par
  anterior desde su `.bak` o, si no había, se borra lo publicado. Resultado: el par anterior byte a byte o
  ningún par. Si la restauración también falla, los `.bak` se conservan para recuperar el par a mano.
- Límite: si el proceso muere de golpe entre los dos `os.replace` (corte de energía, `kill -9`), o si falla la
  restauración, el par puede quedar inconsistente. Se detecta porque `diarization_sha256` del meta no
  coincide con el JSON: `par_vigente()` lo rechaza y `contrato.validar_par` lo informa.
- Un fallo escribe `diarization.error.json` y nunca toca el par anterior.
- Un éxito borra el `diarization.error.json` de un intento anterior.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
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


def _escribir_sincronizado(ruta: Path, contenido: bytes) -> Path:
    with open(ruta, "wb") as f:
        f.write(contenido)
        f.flush()
        os.fsync(f.fileno())
    return ruta


def _escribir_tmp(destino: Path, contenido: bytes) -> Path:
    return _escribir_sincronizado(destino.with_name(destino.name + ".tmp"), contenido)


def _respaldar(destino: Path, marca: str) -> Path:
    """Copia completa (con fsync) del archivo vigente, con un nombre propio de esta ejecución."""
    return _escribir_sincronizado(destino.with_name(f"{destino.name}.{marca}.bak"), destino.read_bytes())


def _revertir(publicados: list[Path], respaldos: dict[Path, Path], error: OSError) -> bool:
    """Deshace lo publicado, del último al primero. Devuelve False si no pudo restaurar todo.

    Con respaldo, `os.replace(.bak → destino)`; sin respaldo (no había par anterior), borra lo publicado.
    Si una restauración falla, deja una nota en `error` y no borra ningún respaldo.
    """
    completo = True
    for destino in reversed(publicados):
        try:
            if destino in respaldos:
                os.replace(respaldos[destino], destino)
            else:
                destino.unlink(missing_ok=True)
        except OSError as e:
            completo = False
            error.add_note(f"No se pudo restaurar {destino.name} ({e}); "
                           f"el respaldo queda en {respaldos.get(destino, '(no había)')}")
    return completo


def escribir_par(carpeta, diarizacion: dict, meta: dict) -> dict:
    """Escribe el par de una ejecución exitosa y devuelve el meta escrito (con `diarization_sha256`).

    1. Escribe `diarization.json.tmp` y `diarization.meta.json.tmp` (con fsync) y, si hay un par vigente,
       sus respaldos `.<marca>.bak`. Si algo falla acá, borra lo creado: el par vigente no se tocó.
    2. Publica con `os.replace` el JSON y después el meta.
    3. Si falla una publicación, revierte (ver `_revertir`) y relanza el `OSError`. Si la reversión
       no se completa, los `.bak` se conservan para recuperar el par a mano.
    """
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    contenido = serializar(diarizacion)
    meta = dict(meta, diarization_sha256=hashlib.sha256(contenido).hexdigest())
    destinos = (carpeta / NOMBRE_JSON, carpeta / NOMBRE_META)
    marca = uuid.uuid4().hex[:12]  # un respaldo de una reversión fallida nunca se pisa
    tmps: list[Path] = []
    respaldos: dict[Path, Path] = {}
    try:
        tmps.append(_escribir_tmp(destinos[0], contenido))
        tmps.append(_escribir_tmp(destinos[1], serializar(meta)))
        for destino in destinos:
            if destino.is_file():
                respaldos[destino] = _respaldar(destino, marca)
    except OSError:
        for archivo in [*tmps, *respaldos.values()]:  # el par vigente queda intacto y sin restos
            archivo.unlink(missing_ok=True)
        raise

    publicados: list[Path] = []
    try:
        for tmp, destino in zip(tmps, destinos):
            os.replace(tmp, destino)
            publicados.append(destino)
    except OSError as error:
        for tmp in tmps:
            tmp.unlink(missing_ok=True)
        if _revertir(publicados, respaldos, error):
            for respaldo in respaldos.values():
                respaldo.unlink(missing_ok=True)
        raise
    for respaldo in respaldos.values():
        respaldo.unlink(missing_ok=True)
    (carpeta / NOMBRE_ERROR).unlink(missing_ok=True)
    return meta


def par_vigente(carpeta) -> dict | None:
    """Meta del par válido de la carpeta, o None.

    Válido: existen los dos archivos, el meta es un objeto JSON y su `diarization_sha256` coincide con el
    SHA-256 de `diarization.json` (misma comprobación que `contrato.validar_par`).
    """
    carpeta = Path(carpeta)
    try:
        contenido = (carpeta / NOMBRE_JSON).read_bytes()
        meta = json.loads((carpeta / NOMBRE_META).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict) or meta.get("diarization_sha256") != hashlib.sha256(contenido).hexdigest():
        return None
    return meta


def run_id_vigente(carpeta) -> str | None:
    """`run_id` del par válido y consistente que hay en la carpeta, o None si no hay uno."""
    meta = par_vigente(carpeta)
    return None if meta is None else meta.get("run_id")


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
