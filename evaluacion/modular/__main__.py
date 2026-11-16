"""Ejecutor de la evaluación modular de la PoC (issue #13).

Uso, desde la raíz del repositorio:
    .venv/bin/python -m evaluacion.modular preparar [--config RUTA]
    .venv/bin/python -m evaluacion.modular inferir  [--config RUTA]
    .venv/bin/python -m evaluacion.modular evaluar  [--config RUTA]

Códigos de salida: 0 terminó · 1 falló (el motivo va a la salida de errores) · 2 paso todavía no implementado.
"""

from __future__ import annotations

import argparse
import sys

from .config import CONFIG_POR_DEFECTO, cargar_config
from .originales import OriginalInvalido, verificar_originales


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m evaluacion.modular",
                                     description="Muestra congelada y evaluación modular de la PoC (§2.3).")
    sub = parser.add_subparsers(dest="comando", required=True)
    for nombre, ayuda in (("preparar", "verificar originales, seleccionar y congelar la muestra"),
                          ("inferir", "correr los módulos sobre la muestra y guardar sus salidas"),
                          ("evaluar", "contratos y métricas desde las salidas guardadas")):
        p = sub.add_parser(nombre, help=ayuda)
        p.add_argument("--config", default=str(CONFIG_POR_DEFECTO), help="configuración TOML")
    return parser


def preparar(args) -> int:
    config = cargar_config(args.config)
    try:
        hashes = verificar_originales(config.originales, config.cache)
    except OriginalInvalido as e:
        print(e, file=sys.stderr)
        return 1
    print(f"{len(hashes)} originales verificados.")
    print("La selección y el manifiesto todavía no están implementados (tareas 3.1 a 4.2).", file=sys.stderr)
    return 2


def no_implementado(args) -> int:
    print(f"`{args.comando}` todavía no está implementado (grupos 5 y 6 de tasks.md).", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    return {"preparar": preparar}.get(args.comando, no_implementado)(args)


if __name__ == "__main__":
    sys.exit(main())
