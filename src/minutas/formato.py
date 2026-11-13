"""Representación Markdown determinística de una minuta validada."""

from __future__ import annotations

import re

from pydantic import BaseModel

from .contratos import Intervencion, SECCIONES_MINUTA


TITULOS_SECCIONES = {
    "resumen": "Resumen",
    "temas": "Temas tratados",
    "decisiones": "Decisiones",
    "problemas": "Problemas identificados",
    "acciones": "Acciones pendientes",
}


def _texto(valor: str) -> str:
    compacto = " ".join(valor.split())
    return re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", compacto)


def _reloj(segundos: float) -> str:
    total = int(segundos)
    horas, resto = divmod(total, 3600)
    minutos, segundos_enteros = divmod(resto, 60)
    return f"{horas:02d}:{minutos:02d}:{segundos_enteros:02d}" if horas else f"{minutos:02d}:{segundos_enteros:02d}"


def a_markdown(minuta: BaseModel, intervenciones: list[Intervencion]) -> str:
    tiempos = {intervencion.id: intervencion.inicio for intervencion in intervenciones}
    partes = ["# Minuta de reunión", ""]
    for seccion in type(minuta).model_fields:
        if seccion not in minuta.model_fields_set:
            continue
        partes.extend([f"## {TITULOS_SECCIONES[seccion]}", ""])
        if seccion == "resumen":
            partes.extend([_texto(minuta.resumen), ""])
            continue
        elementos = getattr(minuta, seccion)
        if not elementos:
            partes.append("No se identificaron elementos.")
        for elemento in elementos:
            linea = f"- [{_reloj(tiempos[elemento.id_ancla])}] {_texto(elemento.texto)}"
            if seccion == "acciones":
                responsable = elemento.responsable or "Sin asignar"
                linea += f" — Responsable: {_texto(responsable)}"
                if elemento.plazo:
                    linea += f"; plazo: {_texto(elemento.plazo)}"
            partes.append(linea)
        partes.append("")
    return "\n".join(partes)