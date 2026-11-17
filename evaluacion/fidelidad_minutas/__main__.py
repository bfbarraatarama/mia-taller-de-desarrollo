"""CLI de preparación y evaluación de minutas."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .archivos import PLANILLAS, SALIDA, carpeta_ejecucion


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluación de recuperación de ítems de minutas.")
    sub = parser.add_subparsers(dest="comando", required=True)
    for nombre in ("preparar", "inferir", "juzgar", "reportar"):
        p = sub.add_parser(nombre)
        p.add_argument("--ejecucion", required=True)
        p.add_argument("--salida", type=Path, default=SALIDA)
        if nombre == "juzgar":
            p.add_argument("--planillas", type=Path, default=PLANILLAS)
    args = parser.parse_args(argv)
    try:
        carpeta = carpeta_ejecucion(args.salida, "evaluacion_minutas", args.ejecucion)
        if args.comando == "preparar":
            from .preparacion import preparar
            carpeta.mkdir(parents=True, exist_ok=False)
            preparar(carpeta / "muestra")
        elif args.comando == "inferir":
            from .inferencia import inferir
            inferir(carpeta)
        elif args.comando == "juzgar":
            from .evaluacion import juzgar
            juzgar(carpeta, args.planillas)
        else:
            from .evaluacion import reportar
            reportar(carpeta)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Error en {args.comando}: {exc}", file=sys.stderr)
        return 1
    print(f"{args.comando}: completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
