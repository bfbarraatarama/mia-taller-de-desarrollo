"""Identidad de entradas y recuperación de copias sin cambiar su procedencia."""
from __future__ import annotations

import json
from pathlib import Path

from ..ingesta.audio import sha256, verificar_wav, FS
from ..rutas import ARCHIVO_AUDIO, ARCHIVO_INGESTA
from .estado import huella


def _manifiesto(carpeta: Path) -> dict:
    datos = json.loads((carpeta / ARCHIVO_INGESTA).read_text(encoding='utf-8'))
    if not isinstance(datos, dict) or not isinstance(datos.get('fuentes'), list) or not datos['fuentes']:
        raise ValueError('Manifiesto de ingesta inválido.')
    return datos


def validar_ingesta(carpeta: Path) -> dict:
    datos = _manifiesto(carpeta)
    muestras = verificar_wav(carpeta / ARCHIVO_AUDIO)
    if (datos.get('version') != 1 or type(datos.get('muestras')) is not int
            or datos['muestras'] != muestras or datos.get('duracion_s') != muestras / FS
            or datos.get('sha256_audio') != sha256(carpeta / ARCHIVO_AUDIO)
            or (datos.get('frecuencia_hz'), datos.get('canales'), datos.get('pcm_bits')) != (FS, 1, 16)):
        raise ValueError('El manifiesto de ingesta no corresponde al audio.')
    offset = 0
    for i, fuente in enumerate(datos['fuentes'], 1):
        ruta = Path(fuente['fuente'])
        if ruta.is_absolute() or not (carpeta / ruta).resolve().is_relative_to(carpeta):
            raise ValueError('Copia de fuente fuera de la reunión.')
        digest = fuente['sha256_fuente']
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Huella de fuente inválida.')
        n = fuente['muestras']
        if (type(n) is not int or n <= 0 or fuente['orden'] != i or fuente['inicio_muestra'] != offset
                or fuente['fin_muestra'] != offset + n or fuente['inicio_s'] != offset / FS
                or fuente['fin_s'] != (offset + n) / FS):
            raise ValueError('Offsets de ingesta inválidos.')
        offset += n
    if offset != muestras:
        raise ValueError('Suma de muestras de ingesta inválida.')
    return datos


def clave_ingesta(originales, hashes) -> str:
    return huella(list(zip(originales, hashes, strict=True)), FS, 1, 16, 'ffmpeg')


def comprobar_identidades(estado: dict, entradas: list) -> None:
    originales = estado['solicitud']['fuentes']
    if not isinstance(originales, list) or not all(isinstance(p, str) for p in originales):
        raise ValueError('Identidades de fuentes inválidas.')
    for original, entrada in zip(originales, entradas, strict=True):
        if entrada.get('ruta_original', original) != original:
            raise ValueError('La ingesta corresponde a otras fuentes.')
    clave = clave_ingesta(originales, [e['sha256_fuente'] for e in entradas])
    if clave != estado['etapas']['preparar']['clave']:
        raise ValueError('La clave de ingesta no corresponde a sus fuentes.')


def conservar_fuentes(carpeta: Path, estado: dict) -> None:
    """Retener el último conjunto de fuentes antes de invalidar el audio."""
    registro = estado['etapas'].get('preparar')
    if not isinstance(registro, dict):
        return
    try:
        if sha256(carpeta / ARCHIVO_INGESTA) == registro['archivos'][ARCHIVO_INGESTA]:
            entradas = _manifiesto(carpeta)['fuentes']
        else:
            raise ValueError('Manifiesto de ingesta alterado')
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        # La versión anterior ya guardaba estas identidades y hashes en la metadata
        # del checkpoint. La clave de ingesta permite comprobar su correspondencia.
        metadata = registro.get('metadata')
        entradas = metadata.get('fuentes') if isinstance(metadata, dict) else None
    if not isinstance(entradas, list):
        return
    try:
        comprobar_identidades(estado, entradas)
        estado['fuentes_conservadas'] = [
            {'original': original, 'copia': entrada['fuente'], 'sha256': entrada['sha256_fuente']}
            for original, entrada in zip(estado['solicitud']['fuentes'], entradas, strict=True)]
    except (ValueError, TypeError, KeyError, AttributeError):
        return


def resolver_fuentes(carpeta: Path, estado: dict, originales: list[Path]) -> tuple[list[Path], list[str]]:
    rutas, hashes = [], []
    for original in originales:
        if original.is_file():
            ruta = original
            digest = sha256(ruta)
        else:
            if original.exists():
                raise ValueError(f'La fuente no es un archivo: {original}')
            opciones = set()
            conservadas = estado.get('fuentes_conservadas', [])
            if not isinstance(conservadas, list):
                raise ValueError('Registro de fuentes conservadas inválido.')
            for entrada in conservadas:
                if not isinstance(entrada, dict) or entrada.get('original') != str(original):
                    continue
                try:
                    relativa = Path(entrada['copia'])
                    copia = (carpeta / relativa).resolve()
                    if (not relativa.is_absolute() and copia.is_relative_to(carpeta) and copia.is_file()
                            and sha256(copia) == entrada['sha256']):
                        opciones.add((copia, entrada['sha256']))
                except (OSError, ValueError, KeyError, TypeError):
                    continue
            if not opciones or len({digest for _, digest in opciones}) != 1:
                raise ValueError(f'Fuente no disponible y sin copia verificable inequívoca: {original}')
            ruta, digest = min(opciones)
        rutas.append(ruta)
        hashes.append(digest)
    return rutas, hashes
