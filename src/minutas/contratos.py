"""Contratos internos, independientes del formato de transcripción del equipo."""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator, model_validator


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Intervencion(_Estricto):
    id: str
    inicio: float
    fin: float
    hablante: str | None
    nombre: str | None
    texto: str = Field(min_length=1)
    superposicion: bool
    ambiguo: bool

    @field_validator("inicio", "fin", mode="before")
    @classmethod
    def tiempo_valido(cls, valor: object) -> float:
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError("El tiempo debe ser numérico, expresado en segundos.")
        if not math.isfinite(valor) or valor < 0:
            raise ValueError("El tiempo debe ser finito y no negativo.")
        return float(valor)

    @field_validator("superposicion", "ambiguo", mode="before")
    @classmethod
    def bandera_valida(cls, valor: object) -> bool:
        if not isinstance(valor, bool):
            raise ValueError("La marca de confianza debe ser booleana.")
        return valor

    @model_validator(mode="after")
    def orden_temporal(self) -> Self:
        if self.fin <= self.inicio:
            raise ValueError("El fin de la intervención debe superar el inicio.")
        return self


class ElementoMinuta(_Estricto):
    texto: str = Field(min_length=1, description="Contenido verificable y conciso en español.")
    ids_intervenciones: list[str] = Field(
        min_length=1, description="Identificadores de intervenciones que respaldan el contenido."
    )
    id_ancla: str = Field(
        min_length=1, description="Intervención principal para la marca temporal del elemento."
    )

    @model_validator(mode="after")
    def ancla_con_evidencia(self) -> Self:
        if self.id_ancla not in self.ids_intervenciones:
            raise ValueError("La intervención principal debe figurar entre las evidencias.")
        if len(self.ids_intervenciones) != len(set(self.ids_intervenciones)):
            raise ValueError("No se permiten referencias de evidencia repetidas.")
        return self


class AccionMinuta(ElementoMinuta):
    responsable: str | None = Field(
        description="Nombre explícito del responsable, o nulo cuando no está identificado."
    )
    plazo: str | None = Field(
        description="Plazo mencionado explícitamente, o nulo cuando no consta."
    )


class MinutaEstructurada(_Estricto):
    resumen: str = Field(min_length=1, description="Síntesis ejecutiva en español.")
    temas: list[ElementoMinuta]
    decisiones: list[ElementoMinuta]
    problemas: list[ElementoMinuta]
    acciones: list[AccionMinuta]


SECCIONES_MINUTA = ("resumen", "temas", "decisiones", "problemas", "acciones")


def validar_secciones(secciones: tuple[str, ...]) -> tuple[str, ...]:
    """Rechaza selecciones vacías, repetidas o ajenas al contrato."""
    if not isinstance(secciones, tuple) or not secciones:
        raise ValueError("Debés seleccionar al menos una sección de minuta.")
    if any(not isinstance(seccion, str) or seccion not in SECCIONES_MINUTA for seccion in secciones):
        raise ValueError(f"Secciones admitidas: {', '.join(SECCIONES_MINUTA)}.")
    if len(set(secciones)) != len(secciones):
        raise ValueError("No pueden repetirse secciones en una misma minuta.")
    return secciones


@lru_cache(maxsize=32)
def modelo_minuta(secciones: tuple[str, ...]) -> type[BaseModel]:
    """Esquema estricto: solo exige y admite las secciones solicitadas."""
    validar_secciones(secciones)
    if secciones == SECCIONES_MINUTA:
        return MinutaEstructurada
    tipos = {
        "resumen": (str, Field(min_length=1, description="Síntesis ejecutiva en español.")),
        "temas": (list[ElementoMinuta], Field(description="Asuntos sustantivos tratados.")),
        "decisiones": (list[ElementoMinuta], Field(description="Acuerdos efectivamente adoptados.")),
        "problemas": (list[ElementoMinuta], Field(description="Problemas y asuntos no resueltos.")),
        "acciones": (list[AccionMinuta], Field(description="Tareas y compromisos explícitos.")),
    }
    return create_model("MinutaSeleccionada", __base__=_Estricto, **{
        seccion: tipos[seccion] for seccion in secciones
    })


def validar_evidencias(minuta: BaseModel, intervenciones: list[Intervencion]) -> None:
    """Comprueba existencia de referencias, no su veracidad semántica."""
    disponibles = {intervencion.id for intervencion in intervenciones}
    for categoria in ("temas", "decisiones", "problemas", "acciones"):
        for indice, elemento in enumerate(getattr(minuta, categoria, []), start=1):
            desconocidos = set(elemento.ids_intervenciones) - disponibles
            if desconocidos:
                raise ValueError(
                    f"{categoria}[{indice}]: referencias inexistentes: {sorted(desconocidos)}"
                )