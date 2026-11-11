"""Catálogo cerrado de modelos seleccionables para generar minutas.

La interfaz presenta `nombre` y conserva `clave` como dato interno. Los
identificadores de los proveedores no forman parte del contrato de la GUI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ModeloMinutas:
    clave: str
    nombre: str
    proveedor: Literal["ollama", "bedrock"]
    identificador: str
    descripcion: str
    requiere_remoto: bool


MODELOS_DISPONIBLES: tuple[ModeloMinutas, ...] = (
    ModeloMinutas(
        clave="qwen2.5-7b",
        nombre="Qwen 2.5 (7B) — local",
        proveedor="ollama",
        identificador="qwen2.5:7b",
        descripcion="Inferencia mediante Ollama en el equipo local.",
        requiere_remoto=False,
    ),
    ModeloMinutas(
        clave="nova-lite",
        nombre="Amazon Nova Lite — Bedrock",
        proveedor="bedrock",
        identificador="us.amazon.nova-lite-v1:0",
        descripcion="Inferencia remota mediante AWS Bedrock (perfil de EE. UU.).",
        requiere_remoto=True,
    ),
    ModeloMinutas(
        clave="claude-opus-4.5",
        nombre="Claude Opus 4.5 — Bedrock",
        proveedor="bedrock",
        identificador="us.anthropic.claude-opus-4-5-20251101-v1:0",
        descripcion="Inferencia remota mediante AWS Bedrock (perfil de EE. UU.).",
        requiere_remoto=True,
    ),
)

MODELO_PREDETERMINADO = "qwen2.5-7b"
_MODELOS_POR_CLAVE = {modelo.clave: modelo for modelo in MODELOS_DISPONIBLES}


def listar_modelos() -> tuple[ModeloMinutas, ...]:
    """Datos declarativos para construir el selector de la interfaz."""
    return MODELOS_DISPONIBLES


def obtener_modelo(clave: str) -> ModeloMinutas:
    """Resuelve exclusivamente una clave del catálogo, nunca un ID libre."""
    if not isinstance(clave, str) or clave not in _MODELOS_POR_CLAVE:
        opciones = ", ".join(_MODELOS_POR_CLAVE)
        raise ValueError(f"Modelo no disponible: {clave!r}. Opciones: {opciones}.")
    return _MODELOS_POR_CLAVE[clave]