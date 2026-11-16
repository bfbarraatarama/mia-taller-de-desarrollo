"""Ejecutor de la evaluación modular de la PoC (issue #13).

Uso, desde la raíz del repositorio:
    .venv/bin/python -m evaluacion.modular preparar [--verificar] [--config RUTA]
    .venv/bin/python -m evaluacion.modular inferir  [--config RUTA]
    .venv/bin/python -m evaluacion.modular evaluar  [--config RUTA]

Códigos de salida: 0 terminó · 1 falló (el motivo va a la salida de errores).
"""

from __future__ import annotations

import argparse
import sys
import time

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
        if nombre == "preparar":
            p.add_argument("--verificar", action="store_true",
                           help="solo comprobar la muestra contra su manifiesto, sin modificar nada")
            p.add_argument("--reemplazar", action="store_true",
                           help="reemplazar la muestra congelada aunque la nueva tenga otro contenido_sha256")
        if nombre == "inferir":
            p.add_argument("--rehacer", action="store_true", help="volver a inferir aunque haya salidas vigentes")
    return parser


def verificar(config) -> int:
    from .muestra import verificar_muestra

    if not config.manifiesto.is_file():
        print(f"No hay manifiesto en {config.manifiesto}: correr `preparar` primero.", file=sys.stderr)
        return 1
    problemas = verificar_muestra(config.manifiesto, config.salida)
    if problemas:
        print("La muestra no coincide con su manifiesto:\n" + "\n".join(f"- {p}" for p in problemas),
              file=sys.stderr)
        return 1
    print(f"Muestra intacta según {config.manifiesto.name}.")
    return 0


def preparar(args) -> int:
    config = cargar_config(args.config)
    if args.verificar:
        return verificar(config)
    inicio = time.time()
    try:
        hashes = verificar_originales(config.originales, config.cache)
    except OriginalInvalido as e:
        print(e, file=sys.stderr)
        return 1
    print(f"{len(hashes)} originales verificados.")
    from .muestra import MuestraDistinta, preparar_muestra, publicar_muestra

    manifiesto, nueva = preparar_muestra(config, hashes)
    try:
        escrito = publicar_muestra(config, manifiesto, nueva, inicio, reemplazar=args.reemplazar)
    except MuestraDistinta as e:
        print(e, file=sys.stderr)
        return 1
    elementos = manifiesto["contenido"]["elementos"]
    estado = "congelada" if escrito else "igual a la congelada (manifiesto sin cambios)"
    print(f"Muestra {estado}: {len(elementos)} elementos, contenido_sha256 {manifiesto['contenido_sha256']}.")
    return 0


def inferir(args) -> int:
    from .inferencia import MuestraAlterada, inferir as correr

    config = cargar_config(args.config)
    try:
        resumen = correr(config, rehacer=args.rehacer, avisar=lambda m: print(m, flush=True))
    except MuestraAlterada as e:
        print(e, file=sys.stderr)
        return 1
    print(f"Inferencia: {resumen['ejecutados']} ejecutados, {resumen['reutilizados']} reutilizados.")
    if resumen.get("fallidos"):
        print("Fallaron: " + ", ".join(resumen["fallidos"]), file=sys.stderr)
        return 1
    return 0


def evaluar(args) -> int:
    import json

    from .contratos import evaluar_contratos
    from .muestra import verificar_muestra

    config = cargar_config(args.config)
    problemas = verificar_muestra(config.manifiesto, config.salida)
    if problemas:
        print("La muestra no coincide con su manifiesto; no se evalúa:\n" + "\n".join(f"- {p}" for p in problemas),
              file=sys.stderr)
        return 1
    reporte = evaluar_contratos(config.manifiesto, config.salida, config.inferencia, config.modelos["secciones"])
    config.resultados.mkdir(parents=True, exist_ok=True)
    (config.resultados / "contratos.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
                                                       encoding="utf-8")
    for modulo, r in reporte["modulos"].items():
        detalle = f"{r['validas']}/{r['total']}" + (f", {len(r['faltantes'])} faltantes" if r["faltantes"] else "")
        print(f"{modulo:12} {detalle} ({r['porcentaje']} %)")
        for v in r["violaciones"]:
            print(f"    {v['archivo']}: {v['regla']}", file=sys.stderr)
    print(f"Funcionamiento modular: {reporte['modulos_al_100']}/4 módulos al 100 % "
          f"({'cumple' if reporte['cumple'] else 'no cumple'}).")
    return 0 if reporte["cumple"] else 1


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    return {"preparar": preparar, "inferir": inferir, "evaluar": evaluar}[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
