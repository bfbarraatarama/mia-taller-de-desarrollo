"""Manifiesto vigente y checkpoints verificables, sin historial de eventos.

Un archivo temporal y os.replace protegen cada transición; los grupos de artefactos
se vuelven a validar tras cortes abruptos y nunca se tratan como transacción global.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from ..ingesta.audio import sha256
from ..rutas import (ARCHIVO_WORKFLOW, ARCHIVO_AUDIO, ARCHIVO_INGESTA, ARCHIVO_DIARIZACION,
                     ARCHIVO_DIARIZACION_META, ARCHIVO_ASR, ARCHIVO_TRANSCRIPCION,
                     ARCHIVO_TRANSCRIPCION_META, ARCHIVO_HABLANTES)

VERSION = 1
DEPENDENCIAS = {
    'preparar': (), 'diarizar': ('preparar',), 'transcribir': ('preparar',),
    'asociar': ('diarizar', 'transcribir'), 'minuta': ('asociar',),
}
ARCHIVOS = {
    'preparar': (ARCHIVO_AUDIO, ARCHIVO_INGESTA),
    'diarizar': (ARCHIVO_DIARIZACION, ARCHIVO_DIARIZACION_META),
    'transcribir': (ARCHIVO_ASR,),
    'asociar': (ARCHIVO_TRANSCRIPCION, ARCHIVO_TRANSCRIPCION_META),
    'minuta': ('minutes.json', 'minutes.md', 'ejecucion_minutas.json'),
}
ESTADOS = {'pendiente', 'procesando', 'esperando_identificacion', 'completado', 'fallido', 'cancelado'}


def invalidar(estado: dict, etapa: str) -> None:
    afectadas = {etapa}
    for nombre, padres in DEPENDENCIAS.items():
        if afectadas.intersection(padres):
            afectadas.add(nombre)
    for nombre in afectadas:
        estado['etapas'].pop(nombre, None)


def huella(*objetos: Any) -> str:
    contenido = json.dumps(objetos, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)
    return hashlib.sha256(contenido.encode('utf-8')).hexdigest()


def leer(carpeta: Path) -> dict:
    ruta = carpeta / ARCHIVO_WORKFLOW
    if not ruta.exists():
        return {'version': VERSION, 'estado': 'pendiente', 'etapas': {}, 'error': None}
    datos = json.loads(ruta.read_text(encoding='utf-8'))
    if (not isinstance(datos, dict) or type(datos.get('version')) is not int
            or datos['version'] != VERSION or not isinstance(datos.get('etapas'), dict)
            or not isinstance(datos.get('estado'), str) or datos['estado'] not in ESTADOS
            or ('solicitud' in datos and not isinstance(datos['solicitud'], dict))
            or (datos['etapas'] and not datos.get('solicitud'))):
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


def _grupo_integro(carpeta: Path, etapa: str, registro: object) -> bool:
    if (not isinstance(registro, dict) or not isinstance(registro.get('clave'), str)
            or len(registro['clave']) != 64 or not isinstance(registro.get('metadata'), dict)):
        return False
    archivos = registro.get('archivos')
    if not isinstance(archivos, dict):
        return False
    esperados = set(ARCHIVOS[etapa])
    try:
        if etapa == 'asociar':
            meta = json.loads((carpeta / ARCHIVO_TRANSCRIPCION_META).read_text(encoding='utf-8'))
            if type(meta.get('etiquetado')) is not bool:
                return False
            if meta['etiquetado']:
                esperados.add(ARCHIVO_HABLANTES)
        return set(archivos) == esperados and all(
            isinstance(digest, str) and (carpeta / nombre).is_file()
            and sha256(carpeta / nombre) == digest for nombre, digest in archivos.items())
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def etapas_vigentes(carpeta: Path, estado: dict, *, comprobar=None) -> set[str]:
    validas = set()
    for etapa, padres in DEPENDENCIAS.items():
        if set(padres) <= validas and _grupo_integro(carpeta, etapa, estado['etapas'].get(etapa)):
            if comprobar is None or comprobar(etapa):
                validas.add(etapa)
    return validas


def vigente(carpeta: Path, estado: dict, etapa: str, clave: str) -> bool:
    registro = estado['etapas'].get(etapa)
    if not isinstance(registro, dict) or registro.get('clave') != clave:
        return False
    vistos = {}

    def visitar(nombre):
        if nombre not in vistos:
            vistos[nombre] = (all(visitar(p) for p in DEPENDENCIAS[nombre])
                              and _grupo_integro(carpeta, nombre, estado['etapas'].get(nombre)))
        return vistos[nombre]

    return visitar(etapa)


def registrar(carpeta: Path, estado: dict, etapa: str, clave: str, archivos: tuple[str, ...],
              metadata: dict | None = None) -> None:
    estado.setdefault('etapas', {})[etapa] = {
        'clave': clave,
        'archivos': {nombre: sha256(carpeta / nombre) for nombre in archivos},
        'metadata': metadata or {},
    }
    publicar(carpeta, estado)


def artefactos_vigentes(carpeta: Path, estado: dict, validas: set[str] | None = None) -> dict[str, str]:
    """Exponer únicamente grupos completos y con todos sus antecesores íntegros."""
    if validas is None:
        validas = etapas_vigentes(carpeta, estado)
    return {nombre: str(carpeta / nombre) for etapa in DEPENDENCIAS if etapa in validas
            for nombre in estado['etapas'][etapa]['archivos']}
