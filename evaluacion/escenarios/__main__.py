"""Escenarios de §2.1 y recuperación ante interrupciones (issue #15).

Uso, desde la raíz del repositorio:
    .venv/bin/python -m evaluacion.escenarios preparar                  # arma y fija las entradas
    .venv/bin/python -m evaluacion.escenarios correr [--escenario 2.1.3] # cada escenario por la aplicación (GPU)
    .venv/bin/python -m evaluacion.escenarios comprobar                 # comprobaciones automáticas y reporte
    pw-jack .venv/bin/python -m evaluacion.escenarios recuperacion      # graba con el micrófono y corta a la fuerza

Códigos de salida: 0 terminó · 1 falló (el motivo va a la salida de errores).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

from .comprobaciones import comprobar
from .entradas import EntradaAlterada, agregar_ruido, construir_manifiesto, verificar_entradas

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).resolve().parent / "config.toml"
ESCENARIOS = ("2.1.2", "2.1.3", "2.1.4", "2.1.5")


def cargar(ruta: Path | str = CONFIG) -> dict:
    with open(ruta, "rb") as f:
        c = tomllib.load(f)
    for clave in ("manifiesto", "resultados", "datos", "corridas", "muestra", "datos_muestra"):
        c[clave] = RAIZ / c[clave]
    return c


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def fuentes(c: dict) -> dict[str, dict]:
    m = c["datos_muestra"]
    sesion = sorted((m / "figshare" / c["fragmentos"]["sesion"]).glob("*/audio.wav"))
    return {
        "2.1.2": {"fuentes": [m / c["superposicion"]["tarea"]],
                  "transformacion": "tarea de la muestra congelada con más habla superpuesta en la referencia"},
        "2.1.3": {"fuentes": [RAIZ / c["icsi"]["archivo"]], "transformacion": "ICSI Bro015 completa, sin cambios"},
        "2.1.4": {"fuentes": [c["datos"] / "2.1.4" / "audio.wav"],
                  "transformacion": f"{c['ruido']['base']} con ruido rosa a {c['ruido']['snr_db']} dB de SNR, "
                                    f"semilla {c['semilla']}"},
        "2.1.5": {"fuentes": sesion, "transformacion": f"sesión {c['fragmentos']['sesion']} completa, "
                                                       f"{len(sesion)} archivos en orden"},
    }


def preparar(c: dict) -> int:
    from evaluacion.modular.muestra import verificar_muestra

    problemas = verificar_muestra(c["muestra"], c["datos_muestra"])
    icsi = RAIZ / c["icsi"]["archivo"]
    if not icsi.is_file():
        problemas.append(f"falta {c['icsi']['archivo']}; para obtenerlo: {c['icsi']['obtener']}")
    elif icsi.stat().st_size != c["icsi"]["bytes"] or _sha(icsi) != c["icsi"]["sha256"]:
        problemas.append(f"{c['icsi']['archivo']}: no coincide con el SHA-256 de la configuración")
    if problemas:
        print("No se pueden armar las entradas:\n" + "\n".join(f"- {p}" for p in problemas), file=sys.stderr)
        return 1
    ruidoso = c["datos"] / "2.1.4" / "audio.wav"
    ruidoso.parent.mkdir(parents=True, exist_ok=True)
    ruidoso.write_bytes(agregar_ruido((c["datos_muestra"] / c["ruido"]["base"]).read_bytes(),
                                      c["ruido"]["snr_db"], c["semilla"]))
    manifiesto = construir_manifiesto(fuentes(c), RAIZ)
    c["manifiesto"].write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for nombre, e in manifiesto["escenarios"].items():
        print(f"{nombre}: {len(e['fuentes'])} archivo(s) fijados")
    return 0


def comando(c: dict, escenario: str, entradas: list[Path], salida: Path) -> list[str]:
    m = c["modelos"]
    return [sys.executable, "-m", "src.pipeline", "ejecutar", *map(str, entradas), "--salida", str(salida),
            "--modelo-stt", m["modelo_stt"], "--dispositivo-stt", m["dispositivo"],
            "--dispositivo-diarizacion", m["dispositivo"], "--modelo", m["modelo_minutas"],
            "--secciones", ",".join(m["secciones"])]


def correr(c: dict, escenarios: list[str], ejecutar=None) -> int:
    try:
        verificar_entradas(c["manifiesto"], RAIZ, estricto=True)
    except EntradaAlterada as e:
        print(e, file=sys.stderr)
        return 1
    manifiesto = json.loads(c["manifiesto"].read_text(encoding="utf-8"))
    fallidos = []
    for nombre in escenarios:
        entradas = [RAIZ / f["ruta"] for f in manifiesto["escenarios"][nombre]["fuentes"]]
        salida = c["corridas"] / nombre
        if salida.exists():  # cada corrida en una carpeta nueva; la anterior se conserva aparte
            anterior = c["corridas"] / f"{nombre}.anterior"
            shutil.rmtree(anterior, ignore_errors=True)
            os.replace(salida, anterior)
        salida.mkdir(parents=True)
        cmd = comando(c, nombre, entradas, salida)
        print(f"{nombre}: {len(entradas)} archivo(s)…", flush=True)
        inicio = time.time()
        if ejecutar:
            codigo = ejecutar(cmd, salida)
        else:
            with open(salida / "corrida.log", "w", encoding="utf-8") as log:
                codigo = subprocess.run(cmd, cwd=RAIZ, stdout=log, stderr=subprocess.STDOUT).returncode
        (salida / "corrida.json").write_text(json.dumps({"escenario": nombre, "codigo": codigo,
                                                          "segundos": round(time.time() - inicio, 1)}) + "\n")
        print(f"    código {codigo} en {time.time() - inicio:.0f} s", flush=True)
        if codigo != 0:
            fallidos.append(nombre)
    return 0  # un escenario puede «fallar e informarlo»: lo juzga comprobar


def comprobar_todos(c: dict) -> int:
    manifiesto = json.loads(c["manifiesto"].read_text(encoding="utf-8"))
    reporte = {"escenarios": {}, "entradas": {k: [f["sha256"] for f in v["fuentes"]]
                                             for k, v in manifiesto["escenarios"].items()}}
    for nombre, e in manifiesto["escenarios"].items():
        carpeta = c["corridas"] / nombre
        if not (carpeta / "corrida.json").is_file():
            reporte["escenarios"][nombre] = {"escenario": nombre, "veredicto_automatico": "sin corrida"}
            continue
        corrida = json.loads((carpeta / "corrida.json").read_text(encoding="utf-8"))
        r = comprobar(nombre, carpeta, [f["sha256"] for f in e["fuentes"]], codigo=corrida["codigo"])
        r["corrida"] = corrida
        reporte["escenarios"][nombre] = r
    c["resultados"].mkdir(parents=True, exist_ok=True)
    (c["resultados"] / "escenarios.json").write_text(json.dumps(reporte, ensure_ascii=False, indent=2) + "\n",
                                                     encoding="utf-8")
    for nombre, r in reporte["escenarios"].items():
        extra = f", {r['pendientes_manuales']} manual(es) pendiente(s)" if r.get("pendientes_manuales") else ""
        print(f"{nombre}: automático {r['veredicto_automatico']}{extra}")
        for ch in r.get("comprobaciones", []):
            print(f"    [{ch['resultado']}] {ch['comprobacion']}: {ch['evidencia']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m evaluacion.escenarios", description="Escenarios de §2.1 (issue #15).")
    sub = p.add_subparsers(dest="comando", required=True)
    for nombre in ("preparar", "correr", "comprobar", "recuperacion"):
        s = sub.add_parser(nombre)
        s.add_argument("--config", default=str(CONFIG))
        if nombre == "correr":
            s.add_argument("--escenario", action="append", choices=ESCENARIOS)
        if nombre == "recuperacion":
            s.add_argument("--segundos", type=float, default=130.0, help="tiempo de grabación antes del corte")
    a = p.parse_args(argv)
    c = cargar(a.config)
    if a.comando == "preparar":
        return preparar(c)
    if a.comando == "correr":
        return correr(c, a.escenario or list(ESCENARIOS))
    if a.comando == "comprobar":
        return comprobar_todos(c)
    from .recuperacion import prueba_de_recuperacion
    return prueba_de_recuperacion(c, a.segundos)


if __name__ == "__main__":
    sys.exit(main())
