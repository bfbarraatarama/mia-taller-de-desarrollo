"""Detecta grabaciones interrumpidas sin alterar WAV ni reportes del capturador."""
from __future__ import annotations

import json
from pathlib import Path

from ..ingesta.audio import verificar_wav


def grabaciones_interrumpidas(carpeta: str | Path) -> list[Path]:
    """Solo ofrece WAV comprobados con metadata 'grabando'; no publica ni repara datos."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        return []
    recuperables: list[Path] = []
    for reporte in sorted(carpeta.glob('*.json')):
        try:
            datos = json.loads(reporte.read_text(encoding='utf-8'))
            if not isinstance(datos, dict) or not str(datos.get('estado', '')).startswith('grabando'):
                continue
            # El nombre no se usa para recorrer rutas fuera de la carpeta elegida.
            nombre = datos.get('archivo')
            if not isinstance(nombre, str) or Path(nombre).name != nombre:
                continue
            audio = carpeta / nombre
            if audio.suffix.lower() != '.wav' or audio.stem != reporte.stem:
                continue
            verificar_wav(audio)
        except (OSError, ValueError, KeyError, TypeError, EOFError):
            continue
        recuperables.append(audio)
    return recuperables
