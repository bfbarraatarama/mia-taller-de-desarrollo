"""Manifiesto vigente y checkpoints verificables, sin historial de eventos.

Un archivo temporal y os.replace protegen cada transición; los grupos de artefactos
se vuelven a validar tras cortes abruptos y nunca se tratan como transacción global.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..ingesta.audio import sha256
from ..rutas import ARCHIVO_WORKFLOW

VERSION = 1


def huella(*objetos: Any) -> str:
    contenido = json.dumps(objetos, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)
    return hashlib.sha256(contenido.encode('utf-8')).hexdigest()


def leer(carpeta: Path) -> dict:
    ruta = carpeta / ARCHIVO_WORKFLOW
    if not ruta.exists():
        return {'version': VERSION, 'estado': 'pendiente', 'etapas': {}, 'error': None}
    datos = json.loads(ruta.read_text(encoding='utf-8'))
    if datos.get('version') != VERSION or not isinstance(datos.get('etapas'), dict):
        raise ValueError(f'Formato de workflow.json no admitido en {carpeta}.')
    return datos


def publicar(carpeta: Path, datos: dict) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    temporal = carpeta / '.workflow.json.tmp'
    try:
        with temporal.open('w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporal, carpeta / ARCHIVO_WORKFLOW)
    finally:
        temporal.unlink(missing_ok=True)


def vigente(carpeta: Path, estado: dict, etapa: str, clave: str) -> bool:
    registro = estado.get('etapas', {}).get(etapa) or {}
    if registro.get('clave') != clave:
        return False
    return bool(registro.get('archivos')) and all(
        (carpeta / nombre).is_file() and sha256(carpeta / nombre) == digest
        for nombre, digest in registro['archivos'].items()
    )


def registrar(carpeta: Path, estado: dict, etapa: str, clave: str, archivos: tuple[str, ...],
              metadata: dict | None = None) -> None:
    estado.setdefault('etapas', {})[etapa] = {
        'clave': clave,
        'archivos': {nombre: sha256(carpeta / nombre) for nombre in archivos},
        'metadata': metadata or {},
    }
    publicar(carpeta, estado)


def artefactos_vigentes(carpeta: Path, estado: dict) -> dict[str, str]:
    """Solo artefactos con hash coincidente; no confiere vigencia a etapas obsoletas."""
    salida = {}
    for etapa, registro in estado.get('etapas', {}).items():
        if registro and all((carpeta / n).is_file() and sha256(carpeta / n) == h
                            for n, h in registro.get('archivos', {}).items()):
            salida.update({n: str(carpeta / n) for n in registro['archivos']})
    return salida
