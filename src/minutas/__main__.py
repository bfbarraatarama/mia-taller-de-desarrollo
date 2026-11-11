"""Invocación autónoma: PYTHONPATH=src python -m minutas ..."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .contratos import SECCIONES_MINUTA, validar_secciones
from .generacion import ConfiguracionMinutas, generar_minuta
from .modelos import MODELO_PREDETERMINADO, listar_modelos


def _secciones_cli(valor: str) -> tuple[str, ...]:
    try:
        return validar_secciones(tuple(seccion.strip() for seccion in valor.split(",")))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    modelos = listar_modelos()
    p = argparse.ArgumentParser(
        description="Generar una minuta desde transcription.json.",
        epilog="Modelos disponibles:\n" + "\n".join(
            f"  {modelo.clave}: {modelo.nombre}" for modelo in modelos
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--entrada", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument(
        "--modelo",
        default=MODELO_PREDETERMINADO,
        choices=[modelo.clave for modelo in modelos],
    )
    p.add_argument("--secciones", type=_secciones_cli, default=SECCIONES_MINUTA,
                   metavar="NOMBRES", help="Secciones, separadas por comas: " + ", ".join(SECCIONES_MINUTA))
    p.add_argument("--permitir-remoto", action="store_true")
    p.add_argument("--sobrescribir", action="store_true")
    p.add_argument("--num-ctx", type=int, default=16384)
    p.add_argument("--max-caracteres-bloque", type=int, default=12000)
    args = p.parse_args(argv)
    try:
        config = ConfiguracionMinutas(
            modelo=args.modelo, permitir_remoto=args.permitir_remoto,
            num_ctx=args.num_ctx, max_caracteres_bloque=args.max_caracteres_bloque,
            secciones=args.secciones,
        )
        resultado = generar_minuta(
            args.entrada, args.salida, configuracion=config, sobrescribir=args.sobrescribir
        )
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Error al generar la minuta: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({clave: str(valor) for clave, valor in asdict(resultado).items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())