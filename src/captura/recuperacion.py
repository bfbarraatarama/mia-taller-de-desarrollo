"""Reconocimiento y decisiones persistentes sobre cortes, sin alterar el audio ni su reporte."""
from __future__ import annotations

import json
import os
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from ..ingesta.audio import sha256, verificar_wav


@dataclass(frozen=True)
class GrabacionInterrumpida:
    audio: Path
    sha256_audio: str
    sha256_reporte: str

    @property
    def marca(self) -> Path:
        return self.audio.with_name(f'.{self.audio.name}.recuperada.json')

    def identidad(self) -> dict:
        return {'version': 1, 'sha256_audio': self.sha256_audio, 'sha256_reporte': self.sha256_reporte}


def _verificar(reporte: Path) -> GrabacionInterrumpida | None:
    carpeta = reporte.parent.resolve()
    try:
        if reporte.is_symlink():
            return None
        huella_reporte = sha256(reporte)
        datos = json.loads(reporte.read_text(encoding='utf-8'))
        if not isinstance(datos, dict) or not isinstance(datos.get('estado'), str) or not datos['estado'].startswith('grabando'):
            return None
        nombre = datos.get('archivo')
        if not isinstance(nombre, str) or Path(nombre).name != nombre:
            return None
        audio = carpeta / nombre
        if audio.is_symlink() or audio.suffix.lower() != '.wav' or audio.stem != reporte.stem:
            return None
        antes = audio.stat()
        verificar_wav(audio)
        digest = sha256(audio)
        despues = audio.stat()
        if ((antes.st_dev, antes.st_ino, antes.st_size, antes.st_mtime_ns)
                != (despues.st_dev, despues.st_ino, despues.st_size, despues.st_mtime_ns)
                or sha256(reporte) != huella_reporte):
            return None
        return GrabacionInterrumpida(audio, digest, huella_reporte)
    except (OSError, ValueError, KeyError, TypeError, EOFError, wave.Error):
        return None


def _marca_decision(grabacion: GrabacionInterrumpida, decision: str) -> dict:
    return {**grabacion.identidad(), 'version': 2, 'decision': decision}


def _decision_registrada(grabacion: GrabacionInterrumpida) -> str | None:
    try:
        if grabacion.marca.is_symlink():
            return None
        datos = json.loads(grabacion.marca.read_text(encoding='utf-8'))
        if datos == grabacion.identidad():
            return 'aceptada'  # compatibilidad con las marcas de versión 1
        for decision in ('aceptada', 'omitida'):
            if datos == _marca_decision(grabacion, decision):
                return decision
    except (OSError, ValueError, TypeError):
        pass
    return None


def consultar_grabaciones_interrumpidas(carpeta: str | Path) -> list[GrabacionInterrumpida]:
    """Ofrece cortes verificables sin una decisión definitiva para su identidad actual."""
    carpeta = Path(carpeta).expanduser().resolve()
    if not carpeta.is_dir():
        return []
    recuperables = []
    for reporte in sorted(carpeta.glob('*.json')):
        if reporte.name.startswith('.'):
            continue
        grabacion = _verificar(reporte)
        if grabacion is not None and _decision_registrada(grabacion) is None:
            recuperables.append(grabacion)
    return recuperables


def grabaciones_interrumpidas(carpeta: str | Path) -> list[Path]:
    """Compatibilidad de la consulta de rutas; para aceptar, conservar la instantánea."""
    return [g.audio for g in consultar_grabaciones_interrumpidas(carpeta)]


def _registrar_decision(grabacion: GrabacionInterrumpida, decision: str) -> Path:
    if _verificar(grabacion.audio.with_suffix('.json')) != grabacion:
        raise ValueError('La grabación o su reporte cambiaron desde que se ofreció la recuperación.')
    if _decision_registrada(grabacion) == decision:
        return grabacion.audio
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=grabacion.audio.parent,
                                         prefix='.recuperacion-', suffix='.tmp', delete=False) as f:
            temporal = Path(f.name)
            json.dump(_marca_decision(grabacion, decision), f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporal, grabacion.marca)
    finally:
        if temporal is not None:
            temporal.unlink(missing_ok=True)
    return grabacion.audio


def aceptar_recuperacion(grabacion: GrabacionInterrumpida) -> Path:
    """Registra aceptación, no una declaración de grabación terminada."""
    return _registrar_decision(grabacion, 'aceptada')


def omitir_aviso_recuperacion(grabacion: GrabacionInterrumpida) -> Path:
    """Deja de ofrecer esta identidad sin cargar ni eliminar la grabación."""
    return _registrar_decision(grabacion, 'omitida')
