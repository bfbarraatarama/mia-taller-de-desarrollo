"""Selección y traducción de las reuniones de AMI para fidelidad."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import random
from pathlib import Path

from evaluacion.modular.traduccion import AMI, AMI_ZIP, Traductor, _datos_ami, modelo_en_cache, preparar_reunion_ami
from src.minutas.entrada import leer_transcripcion

from .archivos import guardar_json, leer_csv, leer_json, sha256, verificar_archivos


def seleccionar(carpeta_ami: Path = AMI) -> list[dict]:
    filas = leer_csv(carpeta_ami / "reuniones.csv")
    elegibles = [f for f in filas if f["tiene_minuta"].lower() == "true"]
    elegibles.sort(key=lambda f: (-float(f["duracion_s"]), f["reunion"]))
    if len(elegibles) < 3:
        raise ValueError("Se necesitan tres reuniones de AMI con minuta.")
    return elegibles[:3]


def preparar(carpeta: Path, *, carpeta_ami: Path = AMI, traductor=None, ami_zip: Path = AMI_ZIP) -> dict:
    archivos_fuente = [carpeta_ami / n for n in ("reuniones.csv", "turnos.parquet", "minutas.parquet")]
    archivos_fuente.append(ami_zip)
    fuentes = {p.name: sha256(p) for p in archivos_fuente}
    reuniones = seleccionar(carpeta_ami)
    for fila in reuniones:
        turnos, items = _datos_ami(fila["reunion"], carpeta_ami)
        if not turnos or not items:
            raise ValueError(f"Faltan turnos o ítems de referencia para {fila['reunion']}.")
    if traductor is None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        import numpy as np
        import torch

        random.seed(0)
        np.random.seed(0)
        torch.manual_seed(0)
        torch.use_deterministic_algorithms(True)
        if not modelo_en_cache():
            raise RuntimeError("Falta MarianMT en la caché local; prepará el modelo antes de ejecutar.")
        traductor = Traductor("cpu")
    from evaluacion.modular.traduccion import roles_ami

    carpeta.mkdir(parents=True, exist_ok=False)
    registros = []
    for fila in reuniones:
        reunion = fila["reunion"]
        turnos, items = _datos_ami(reunion, carpeta_ami)
        destino = carpeta / "ami" / reunion
        registro = preparar_reunion_ami(reunion, destino, traductor, turnos=turnos, items=items,
                                        roles=roles_ami(reunion, ami_zip))
        leer_transcripcion(destino / "transcription.json")
        referencia = leer_json(destino / "referencia_minuta.json")["items"]
        ids = [r["item_id"] for r in referencia]
        if not ids or len(ids) != len(set(ids)) or any(not r["texto"] for r in referencia):
            raise ValueError(f"Referencias vacías o duplicadas en {reunion}.")
        registros.append({**registro, "duracion_s": float(fila["duracion_s"]), "palabras": int(fila["palabras"])})
    versiones = {}
    for paquete in ("torch", "transformers", "numpy", "pandas"):
        try:
            versiones[paquete] = importlib.metadata.version(paquete)
        except importlib.metadata.PackageNotFoundError:
            versiones[paquete] = None
    manifiesto = {"version_esquema": 1, "seleccion": "tres mayores duraciones con minuta; empate por ID",
                  "fuentes_sha256": fuentes, "python": platform.python_version(),
                  "versiones": versiones, "reuniones": registros}
    guardar_json(carpeta / "manifiesto.json", manifiesto)
    return manifiesto


def verificar(carpeta: Path) -> dict:
    manifiesto = leer_json(carpeta / "manifiesto.json")
    for registro in manifiesto["reuniones"]:
        verificar_archivos(carpeta / "ami" / registro["reunion"], registro["archivos"])
    return manifiesto
