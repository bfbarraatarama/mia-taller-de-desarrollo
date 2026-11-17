"""Construcción de cortes equilibrados de los bloques realmente procesados."""

from __future__ import annotations

from dataclasses import asdict

from src.minutas.experimento import Bloque, Ocurrencia, partir as partir


def serializar(bloques: tuple[Bloque, ...] | list[Bloque]) -> list[dict]:
    return [{**asdict(b), "caracteres_texto": sum(o.fin_texto - o.inicio_texto for o in b.ocurrencias)}
            for b in bloques]


def deserializar(datos: list[dict]) -> tuple[Bloque, ...]:
    bloques = []
    for fila in datos:
        ocurrencias = tuple(Ocurrencia(**o) for o in fila["ocurrencias"])
        if fila["caracteres_texto"] != sum(o.fin_texto - o.inicio_texto for o in ocurrencias):
            raise ValueError("El tamaño del bloque no coincide con sus ocurrencias.")
        bloques.append(Bloque(fila["bloque_id"], ocurrencias, fila.get("padre_id"), fila.get("lado")))
    return tuple(bloques)
