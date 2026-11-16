"""Rutas y nombres de artefactos compartidos por las etapas de la PoC."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json


DIRECTORIO_SRC = Path(__file__).resolve().parent
DIRECTORIO_PROYECTO = DIRECTORIO_SRC.parent
DIRECTORIO_PROMPTS_MINUTAS = DIRECTORIO_SRC / "minutas" / "prompts"

PROMPT_EXTRACCION_MINUTAS = DIRECTORIO_PROMPTS_MINUTAS / "extraccion_v1.md"
PROMPT_CONSOLIDACION_MINUTAS = DIRECTORIO_PROMPTS_MINUTAS / "consolidacion_v1.md"
DEFINICIONES_SECCIONES_MINUTAS = DIRECTORIO_PROMPTS_MINUTAS / "secciones_v1.json"

ARCHIVO_ENTORNO_PROYECTO = DIRECTORIO_PROYECTO / ".env"

# Salida de la etapa 3 (STT) y entrada de la etapa 4.
ARCHIVO_ASR = "asr.json"


@dataclass(frozen=True)
class RutasResultadoMinutas:
    json: Path
    markdown: Path
    manifiesto: Path


def rutas_resultado_minutas(directorio_salida: str | Path) -> RutasResultadoMinutas:
    """Las rutas dependen del directorio elegido por el usuario, no de la GUI."""
    directorio = Path(directorio_salida)
    return RutasResultadoMinutas(
        json=directorio / "minutes.json",
        markdown=directorio / "minutes.md",
        manifiesto=directorio / "ejecucion_minutas.json",
    )


def rutas_entorno() -> tuple[Path, ...]:
    """Respeta primero el .env del directorio de ejecución y luego el del repo."""
    return tuple(dict.fromkeys((Path.cwd() / ".env", ARCHIVO_ENTORNO_PROYECTO)))
# Las rutas de trabajo son configurables en cada solicitud, pero siempre tienen un default canónico.
DIRECTORIO_RESULTADOS_PREDETERMINADO = DIRECTORIO_PROYECTO / "resultados"
DIRECTORIO_GRABACIONES_PREDETERMINADO = DIRECTORIO_RESULTADOS_PREDETERMINADO / "grabaciones"
ARCHIVO_AUDIO = "audio.wav"
ARCHIVO_INGESTA = "ingesta.json"
ARCHIVO_DIARIZACION = "diarization.json"
ARCHIVO_DIARIZACION_META = "diarization.meta.json"
ARCHIVO_TRANSCRIPCION = "transcription.json"
ARCHIVO_TRANSCRIPCION_META = "transcription.meta.json"
ARCHIVO_HABLANTES = "speakers.json"
ARCHIVO_WORKFLOW = "workflow.json"


def directorio_reunion(ruta: str | Path | None = None, *,
                      fuentes: tuple[str | Path, ...] = ()) -> Path:
    """Carpeta por reunión bajo el destino predeterminado, o destino explícito.

    Un conjunto ordenado de fuentes determina siempre la misma carpeta por defecto:
    reintentar no crea directorios nuevos y dos reuniones no se pisan entre sí.
    """
    base = Path(ruta).expanduser().resolve() if ruta is not None else DIRECTORIO_RESULTADOS_PREDETERMINADO
    if base == DIRECTORIO_RESULTADOS_PREDETERMINADO and fuentes:
        identidades = [str(Path(p).expanduser().resolve()) for p in fuentes]
        huella = hashlib.sha256(json.dumps(identidades, ensure_ascii=False).encode('utf-8')).hexdigest()[:12]
        return base / f'reunion-{huella}'
    return base
