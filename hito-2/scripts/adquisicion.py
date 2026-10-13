"""Primitivas de adquisición verificable. Sin dependencias de terceros."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

TEMP_CODES = {408, 425, 429, 500, 502, 503, 504}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def validar(ruta: Path, esperado: dict | None) -> bool:
    if not ruta.is_file() or ruta.stat().st_size == 0:
        return False
    if not esperado or not esperado.get("sha256") or not esperado.get("bytes"):
        return False
    return (
        ruta.stat().st_size == esperado["bytes"]
        and sha256(ruta) == esperado["sha256"]
    )


def verificar_zip(ruta: Path) -> None:
    if ruta.suffix.lower() == ".zip":
        with zipfile.ZipFile(ruta) as z:
            malo = z.testzip()
        if malo is not None:
            raise ValueError(f"ZIP corrupto: {ruta}: {malo}")


def guardar_json(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, ruta)


def cargar_json(ruta: Path, defecto: dict | None = None) -> dict:
    if not ruta.exists():
        return {} if defecto is None else defecto
    return json.loads(ruta.read_text(encoding="utf-8"))


def registro(
    ruta: Path,
    raiz: Path,
    lock: dict,
    esperado: dict | None = None,
) -> dict:
    """Acepta únicamente archivos con integridad verificable."""
    clave = ruta.relative_to(raiz).as_posix()
    dato = lock.get("archivos", {}).get(clave) or esperado

    if not validar(ruta, dato):
        raise ValueError(f"Sin integridad verificable: {clave}")

    verificar_zip(ruta)
    return dato


def bajar(
    url: str,
    destino: Path,
    esperado: dict | None = None,
    *,
    intentos: int = 3,
    abrir=None,
    md5_esperado: str | None = None,
    bytes_esperados: int | None = None,
) -> dict:
    """Descarga atómica con validación y reanudación controlada."""
    abrir = abrir or urllib.request.urlopen

    def verificar_oficial(ruta: Path) -> None:
        if bytes_esperados is not None and ruta.stat().st_size != bytes_esperados:
            raise ValueError(f"Tamaño diferente del publicado: {ruta}")
        if md5_esperado is not None:
            resumen = hashlib.md5()
            with ruta.open("rb") as f:
                for bloque in iter(lambda: f.read(1024 * 1024), b""):
                    resumen.update(bloque)
            if resumen.hexdigest() != md5_esperado.lower():
                raise ValueError(f"MD5 diferente del publicado: {ruta}")

    if destino.exists():
        if esperado:
            if not validar(destino, esperado):
                raise ValueError(f"Existe un archivo sin hash válido: {destino}")
        elif md5_esperado is None or bytes_esperados is None:
            raise ValueError(f"Existe un archivo sin hash válido: {destino}")
        verificar_oficial(destino)
        verificar_zip(destino)
        return {"bytes": destino.stat().st_size, "sha256": sha256(destino)}

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".part")

    # Sin checksum previo, no es seguro combinar respuestas de
    # potencialmente distintas versiones remotas.
    if temporal.exists() and not (
        (esperado and esperado.get("sha256"))
        or (md5_esperado and bytes_esperados)
    ):
        temporal.unlink()
    ultimo = None

    for intento in range(intentos):
        posicion = temporal.stat().st_size if temporal.exists() else 0
        encabezados = {"User-Agent": "hito2-viabilidad/2.0"}

        if posicion:
            encabezados["Range"] = f"bytes={posicion}-"

        req = urllib.request.Request(url, headers=encabezados)

        try:
            with abrir(req, timeout=120) as respuesta:
                codigo = respuesta.status

                if posicion:
                    cr = respuesta.headers.get("Content-Range", "")
                    m = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", cr)

                    if codigo == 200:
                        temporal.unlink()
                        posicion = 0
                    elif codigo != 206 or not m or int(m[1]) != posicion:
                        raise ValueError(f"Content-Range inválido: {cr!r}")
                    elif int(m[2]) + 1 != int(m[3]):
                        raise ValueError(f"Content-Range incompleto: {cr!r}")

                elif codigo != 200:
                    raise ValueError(f"HTTP inesperado: {codigo}")

                longitud = respuesta.headers.get("Content-Length")
                longitud = int(longitud) if longitud is not None else None

                if longitud is None and not esperado and md5_esperado is None:
                    raise ValueError(
                        "Sin Content-Length ni checksum autoritativo"
                    )

                modo = "ab" if posicion else "wb"
                recibidos = 0

                with temporal.open(modo) as f:
                    while bloque := respuesta.read(1024 * 1024):
                        f.write(bloque)
                        recibidos += len(bloque)
                        if bytes_esperados is not None and posicion + recibidos > bytes_esperados:
                            raise ValueError("Descarga supera tamaño publicado")

                if longitud is not None and recibidos != longitud:
                    raise OSError(
                        f"Descarga incompleta: {recibidos} de {longitud} bytes"
                    )

                if temporal.stat().st_size == 0:
                    raise ValueError("Descarga vacía")

                if destino.suffix.lower() == ".csv":
                    with temporal.open("rb") as f:
                        comienzo = f.read(256).lstrip().lower()
                    if comienzo.startswith((b"<!doctype html", b"<html")):
                        raise ValueError(
                            "El servidor devolvió HTML en lugar de CSV"
                        )

                if esperado and not validar(temporal, esperado):
                    raise ValueError(
                        "Checksum o tamaño diferente del valor fijado"
                    )
                verificar_oficial(temporal)

                if destino.suffix.lower() == ".zip":
                    with zipfile.ZipFile(temporal) as z:
                        malo = z.testzip()
                    if malo is not None:
                        raise ValueError(f"ZIP corrupto: {malo}")

                datos = {
                    "bytes": temporal.stat().st_size,
                    "sha256": sha256(temporal),
                }
                os.replace(temporal, destino)
                return datos

        except urllib.error.HTTPError as e:
            if e.code not in TEMP_CODES:
                raise
            ultimo = e

        except (OSError, urllib.error.URLError) as e:
            ultimo = e

        if intento + 1 < intentos:
            time.sleep(0.5 * (2 ** intento))

    raise RuntimeError(f"No se pudo descargar {destino}: {ultimo}")


def pedir_rango(
    url: str,
    a: int,
    b: int,
    *,
    abrir=None,
) -> tuple[bytes, int]:
    """Exige HTTP 206 y Content-Range coincidente."""
    if a < 0 or b < a:
        raise ValueError("Rango inválido")

    abrir = abrir or urllib.request.urlopen
    req = urllib.request.Request(
        url,
        headers={
            "Range": f"bytes={a}-{b}",
            "User-Agent": "hito2-viabilidad/2.0",
        },
    )

    with abrir(req, timeout=120) as r:
        cr = r.headers.get("Content-Range", "")
        m = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", cr)

        if r.status != 206 or not m:
            raise ValueError(
                f"Servidor no entregó el rango exacto: {r.status} {cr!r}"
            )

        if tuple(map(int, m.groups()[:2])) != (a, b):
            raise ValueError(f"Rango recibido incorrecto: {cr!r}")

        total = int(m[3])
        if b >= total:
            raise ValueError("Rango excede el archivo")

        datos = r.read()

    if len(datos) != b - a + 1:
        raise ValueError("Respuesta parcial truncada")

    return datos, total


def incorporar_local(
    origen: Path,
    destino: Path,
    esperado: dict | None = None,
) -> dict:
    """Incorpora archivos descargados mediante SDK oficiales."""
    if destino.exists():
        if not validar(destino, esperado):
            raise ValueError(
                f"Destino existente no verificado: {destino}"
            )
        verificar_zip(destino)
        return esperado.copy()

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".part")
    shutil.copyfile(origen, temporal)

    if temporal.stat().st_size == 0:
        raise ValueError(f"Origen vacío: {origen}")

    if esperado and not validar(temporal, esperado):
        raise ValueError(f"Checksum distinto: {destino}")

    if destino.suffix.lower() == ".zip":
        with zipfile.ZipFile(temporal) as z:
            malo = z.testzip()
        if malo is not None:
            raise ValueError(f"ZIP corrupto: {malo}")

    datos = {
        "bytes": temporal.stat().st_size,
        "sha256": sha256(temporal),
    }

    os.replace(temporal, destino)
    return datos