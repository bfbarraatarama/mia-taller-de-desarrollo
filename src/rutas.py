"""Rutas y nombres de artefactos compartidos por las etapas de la PoC."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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