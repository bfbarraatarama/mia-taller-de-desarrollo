"""Configuración versionada de la evaluación modular (`config.toml`)."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .originales import Original

RAIZ = Path(__file__).resolve().parents[2]
CONFIG_POR_DEFECTO = RAIZ / "evaluacion" / "modular" / "config.toml"
LOCK = RAIZ / "hito-2" / "fuentes.lock.json"
REGISTRO = RAIZ / "hito-2" / "fuentes.toml"


@dataclass(frozen=True)
class Config:
    semilla: int
    cache: Path
    salida: Path
    manifiesto: Path
    inferencia: Path
    resultados: Path
    salidas: Path
    modelos: dict
    originales: dict[str, Original]


def _esperado(clave: str, registro: list[str] | None, lock: dict, fuentes: dict) -> tuple[int, str | None, str | None]:
    """(bytes, sha256, md5): primero el lock del Hito 2; si no está fijado, el MD5 publicado en fuentes.toml."""
    fijado = lock.get("archivos", {}).get(clave)
    if fijado:
        return fijado["bytes"], fijado["sha256"], None
    if registro:
        datos = fuentes
        for parte in registro:
            datos = datos[parte]
        return datos["bytes"], None, datos["md5"]
    raise ValueError(f"{clave}: sin hash fijado en {LOCK.name} ni registro en {REGISTRO.name}")


def cargar_config(ruta: Path | str = CONFIG_POR_DEFECTO) -> Config:
    with open(ruta, "rb") as f:
        datos = tomllib.load(f)
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    with open(REGISTRO, "rb") as f:
        fuentes = tomllib.load(f)
    originales = {}
    for nombre, o in datos["originales"].items():
        tamano, sha, md5 = _esperado(o["clave"], o.get("registro"), lock, fuentes)
        originales[nombre] = Original(nombre=nombre, clave=o["clave"], bytes=tamano, sha256=sha, md5=md5,
                                      obtener=o["obtener"])
    return Config(semilla=int(datos["semilla"]), cache=RAIZ / datos["cache"], salida=RAIZ / datos["salida"],
                  manifiesto=RAIZ / datos["manifiesto"],
                  inferencia=RAIZ / datos["inferencia"], resultados=RAIZ / datos["resultados"],
                  salidas=RAIZ / datos["salidas"],
                  modelos=dict(datos["modelos"]),
                  originales=originales)
