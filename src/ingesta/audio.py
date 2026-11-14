"""Entrada reproducible de una reunión: normalización PCM16, mono, 16 kHz y unión ordenada.

FFmpeg decodifica fuentes no WAV; la biblioteca estándar calcula duración y offsets a partir de
muestras, sin redondear timestamps de los contenedores. Las fuentes se copian una sola vez al
espacio de la reunión, permitiendo su reconstrucción sin depender de rutas personales.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Sequence

from ..rutas import ARCHIVO_AUDIO, ARCHIVO_INGESTA

FS = 16000


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open('rb') as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def verificar_wav(ruta: Path) -> int:
    with wave.open(str(ruta), 'rb') as archivo:
        if (archivo.getframerate(), archivo.getnchannels(), archivo.getsampwidth(), archivo.getcomptype()) != (FS, 1, 2, 'NONE'):
            raise ValueError(f'{ruta}: se requiere WAV PCM16 mono a 16000 Hz')
        muestras = archivo.getnframes()
        if muestras <= 0:
            raise ValueError(f'{ruta}: audio sin muestras')
        # Se valida que las muestras reales existen; wave.getnframes lee solo la cabecera.
        restantes = muestras
        while restantes:
            bloque = archivo.readframes(min(restantes, 1 << 16))
            if not bloque or len(bloque) % 2:
                raise ValueError(f'{ruta}: datos PCM truncados')
            restantes -= len(bloque) // 2
        return muestras


def _publicar_json(ruta: Path, contenido: dict) -> None:
    temporal = ruta.with_name(ruta.name + '.tmp')
    try:
        with temporal.open('w', encoding='utf-8') as archivo:
            json.dump(contenido, archivo, indent=2, ensure_ascii=False)
            archivo.write('\n')
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, ruta)
    finally:
        temporal.unlink(missing_ok=True)


def ingestar(fuentes: Sequence[str | Path], reunion: str | Path, *,
             identidades: Sequence[Path] | None = None, hashes: Sequence[str] | None = None) -> dict:
    """Crea un solo audio.wav y manifiesto, conservando el orden recibido.

    No modifica la fuente. Si la fuente ya se encuentra en el directorio de reunión,
    se referencia en su ubicación y no se duplica.
    """
    if not fuentes:
        raise ValueError('La reunión requiere al menos un archivo de audio.')
    carpeta = Path(reunion).resolve()
    fuentes_absolutas = [Path(x).expanduser().resolve(strict=True) for x in fuentes]
    identidades = list(identidades) if identidades is not None else fuentes_absolutas
    if len(identidades) != len(fuentes_absolutas) or (hashes is not None and len(hashes) != len(fuentes_absolutas)):
        raise ValueError('Las identidades y hashes deben corresponder a todas las fuentes.')
    if any(not f.is_file() for f in fuentes_absolutas):
        raise ValueError('Todas las entradas deben ser archivos.')
    if any(f == carpeta / ARCHIVO_AUDIO for f in fuentes_absolutas):
        raise ValueError('audio.wav de salida no puede utilizarse como fuente de esa misma reunión.')
    carpeta.mkdir(parents=True, exist_ok=True)
    directorio_fuentes = carpeta / 'fuentes'
    directorio_fuentes.mkdir(exist_ok=True)
    audios = []
    partes = []
    acumulado = 0
    with tempfile.TemporaryDirectory(dir=carpeta, prefix='.ingesta-') as temporal:
        for i, original in enumerate(fuentes_absolutas, start=1):
            identidad = identidades[i - 1]
            hash_original = sha256(original)
            if hashes is not None and hash_original != hashes[i - 1]:
                raise IOError(f'Cambió la fuente antes de normalizar: {identidad.name}')
            if original.is_relative_to(carpeta):
                fuente = original
            else:
                fuente = directorio_fuentes / f'{i:03d}-{identidad.name}'
                # No destruir una copia que aún puede ser necesaria para recuperar otro orden.
                if fuente.exists() and sha256(fuente) != hash_original:
                    fuente = directorio_fuentes / f'{i:03d}-{hash_original}{identidad.suffix}'
                if not fuente.exists() or sha256(fuente) != hash_original:
                    parcial = Path(temporal) / f'{i:03d}.fuente'
                    shutil.copyfile(original, parcial)
                    if sha256(parcial) != hash_original:
                        raise IOError(f'Cambió el archivo de origen durante la copia: {original.name}')
                    os.replace(parcial, fuente)
            normalizado = Path(temporal) / f'{i:03d}.wav'
            comando = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(fuente),
                       '-vn', '-ac', '1', '-ar', str(FS), '-c:a', 'pcm_s16le', '-f', 'wav', str(normalizado)]
            try:
                resultado = subprocess.run(comando, capture_output=True, text=True, timeout=None, check=False)
            except FileNotFoundError as exc:
                raise RuntimeError('FFmpeg no está instalado o no figura en PATH.') from exc
            if resultado.returncode:
                raise ValueError(f'No se pudo normalizar {fuente.name}: {resultado.stderr[-1600:]}')
            if sha256(fuente) != hash_original:
                raise IOError(f'Cambió la fuente durante la normalización: {identidad.name}')
            muestras = verificar_wav(normalizado)
            partes.append(normalizado)
            audios.append({'orden': i, 'fuente': str(fuente.relative_to(carpeta)), 'nombre_original': identidad.name, 'ruta_original': str(identidad),
                           'sha256_fuente': hash_original, 'muestras': muestras,
                           'inicio_muestra': acumulado, 'fin_muestra': acumulado + muestras,
                           'inicio_s': acumulado / FS, 'fin_s': (acumulado + muestras) / FS})
            acumulado += muestras
        temporal_final = Path(temporal) / 'audio_final.wav'
        with wave.open(str(temporal_final), 'wb') as destino:
            destino.setparams((1, 2, FS, 0, 'NONE', 'not compressed'))
            for p in partes:
                with wave.open(str(p), 'rb') as entrada:
                    while bloque := entrada.readframes(1 << 16):
                        destino.writeframesraw(bloque)
        if verificar_wav(temporal_final) != acumulado:
            raise AssertionError('La suma de muestras no coincide con el WAV combinado.')
        os.replace(temporal_final, carpeta / ARCHIVO_AUDIO)
    manifiesto = {'version': 1, 'frecuencia_hz': FS, 'canales': 1, 'pcm_bits': 16,
                  'muestras': acumulado, 'duracion_s': acumulado / FS, 'fuentes': audios,
                  'sha256_audio': sha256(carpeta / ARCHIVO_AUDIO)}
    _publicar_json(carpeta / ARCHIVO_INGESTA, manifiesto)
    return manifiesto
