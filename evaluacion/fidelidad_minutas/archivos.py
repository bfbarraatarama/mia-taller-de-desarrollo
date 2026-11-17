"""Lectura y escritura de artefactos de la evaluación."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "evaluacion/fidelidad_minutas/resultados"
PLANILLAS = RAIZ / "evaluacion/modular/resultados/planillas"
REUNIONES_EJEMPLO = ("IB4005", "IS1009c", "TS3009a")


def carpeta_ejecucion(salida: Path, clase: str, identificador: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}", identificador):
        raise ValueError("El identificador de ejecución debe contener solo letras, números, guiones y guiones bajos.")
    return Path(salida) / clase / identificador


def sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def guardar_json(ruta: Path, datos: Any) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")


def leer_json(ruta: Path) -> dict:
    with ruta.open(encoding="utf-8") as f:
        datos = json.load(f)
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta.name} debe contener un objeto JSON.")
    return datos


def guardar_csv(ruta: Path, columnas: tuple[str, ...], filas: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("x", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas, extrasaction="raise")
        escritor.writeheader()
        escritor.writerows(filas)


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def verificar_archivos(carpeta: Path, archivos: dict[str, str]) -> None:
    for nombre, esperado in archivos.items():
        ruta = carpeta / nombre
        if not ruta.is_file() or sha256(ruta) != esperado:
            raise ValueError(f"Archivo ausente o alterado: {ruta}.")
