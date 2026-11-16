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
    from .muestra import escribir_manifiesto, preparar_muestra

    manifiesto = preparar_muestra(config, hashes)
    escribir_manifiesto(config.manifiesto, manifiesto, inicio)
    elementos = manifiesto["contenido"]["elementos"]
    print(f"Muestra congelada: {len(elementos)} elementos, contenido_sha256 {manifiesto['contenido_sha256']}.")
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


def metricas(config, manifiesto: dict) -> None:
    """Métricas sin umbral (grupo 6) desde las salidas guardadas; cada una en su reporte de `resultados/`."""
    import json

    from .metricas_stt import metricas_stt

    elementos = manifiesto["contenido"]["elementos"]
    stt = metricas_stt(elementos, config.inferencia, config.cache)
    stt["contenido_sha256_muestra"] = manifiesto["contenido_sha256"]
    (config.resultados / "metricas_stt.json").write_text(json.dumps(stt, ensure_ascii=False, indent=2) + "\n",
                                                         encoding="utf-8")
    from .metricas_diar import metricas_diarizacion

    diar = metricas_diarizacion(elementos, config.inferencia, config.cache)
    diar["contenido_sha256_muestra"] = manifiesto["contenido_sha256"]
    (config.resultados / "metricas_diarizacion.json").write_text(
        json.dumps(diar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for sesion, r in [*diar["por_sesion"].items(), ("total", diar["total"])]:
        if r and r["der_estricto"]["valor"] is not None:
            print(f"Diarización {sesion:6} DER {r['der_estricto']['valor']:.3f}  DER NIST "
                  f"{r['der_tolerancia']['valor']:.3f}  JER {r['jer']['valor']:.3f}")
    from .metricas_asociacion import metricas_asociacion

    asoc = metricas_asociacion(elementos, config.inferencia, config.cache)
    asoc["contenido_sha256_muestra"] = manifiesto["contenido_sha256"]
    (config.resultados / "metricas_asociacion.json").write_text(
        json.dumps(asoc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if asoc["total"]:
        t = asoc["total"]
        print(f"Asociación: {t['todas']['porcentaje']} % de palabras bien atribuidas "
              f"(sin superposición {t['sin_superposicion']['porcentaje']} %, "
              f"con superposición {t['con_superposicion']['porcentaje']} %)")
    from .exposicion import informe_exposicion

    exposicion = informe_exposicion(manifiesto)
    (config.resultados / "exposicion.json").write_text(json.dumps(exposicion, ensure_ascii=False, indent=2) + "\n",
                                                       encoding="utf-8")
    for pendiente in exposicion["pendientes"]:
        print(f"Exposición a confirmar: {pendiente}")

    from .planilla import planillas_de_minutas

    planilla = planillas_de_minutas(elementos, config.salida, config.inferencia, config.resultados / "planillas")
    planilla["contenido_sha256_muestra"] = manifiesto["contenido_sha256"]
    (config.resultados / "planilla_minutas.json").write_text(
        json.dumps(planilla, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    t = planilla["total"]
    print(f"Minutas: {t['recuperados']} de {t['marcados']} ítems marcados recuperados; "
          f"{t['pendientes']} de {t['items']} sin marcar (resultados/planillas/)")
    for aviso in planilla["avisos"]:
        print(f"Aviso: {aviso}", file=sys.stderr)
    for fuente, r in sorted(stt["por_fuente"].items()):
        if r["wer"] is not None:
            print(f"STT {fuente:13} WER {r['wer']:.3f}  CER {r['cer']:.3f}  ({r['palabras_referencia']} palabras)")


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
    reporte = evaluar_contratos(config.manifiesto, config.salida, config.inferencia)
    config.resultados.mkdir(parents=True, exist_ok=True)
    (config.resultados / "contratos.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
                                                       encoding="utf-8")
    from .exposicion import ExposicionIncompleta
    from .planilla import PlanillaInvalida

    try:
        metricas(config, json.loads(config.manifiesto.read_text(encoding="utf-8")))
    except (PlanillaInvalida, ExposicionIncompleta) as e:
        print(e, file=sys.stderr)
        return 1
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
