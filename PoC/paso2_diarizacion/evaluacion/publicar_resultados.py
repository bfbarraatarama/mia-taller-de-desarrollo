"""Copia los resultados de la evaluación de calidad a una carpeta versionada (`evaluacion/resultados/`).

`tests/reportes/` queda fuera de git porque tiene salidas locales: el meta de cada corrida incluye la ruta absoluta
del audio. Este script publica lo necesario para revisar y reproducir la evaluación, sin audio ni rutas locales:
- `calidad_<sesion>.json` y `calidad_total.json`, tal como los escribió `pytest -m calidad`;
- `hipotesis_<sesion>/<recording_id>.json`: el `diarization.json` de la corrida principal de cada grabación,
  copiado sin cambios y verificado contra el `diarization_sha256` del reporte.

No ejecuta pyannote ni recalcula métricas. Falla sin escribir nada si falta un archivo, un SHA-256 no coincide
o algún JSON contiene una ruta absoluta.

    python PoC/paso2_diarizacion/evaluacion/publicar_resultados.py [--sesion S26]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

MODULO = Path(__file__).resolve().parents[1]
REPORTES = MODULO / "tests" / "reportes"
DESTINO = Path(__file__).resolve().parent / "resultados"
RUTA_ABSOLUTA = re.compile(r'"(?:[A-Za-z]:[\\/]|/(?:home|Users|mnt|tmp)/)')


class ErrorPublicacion(Exception):
    pass


def preparar(sesion: str = "S26", reportes: Path = REPORTES) -> dict[str, bytes]:
    """{ruta relativa en resultados/: contenido} verificado; no escribe nada."""
    archivos = {}
    for nombre in (f"calidad_{sesion}.json", "calidad_total.json"):
        ruta = reportes / nombre
        if not ruta.is_file():
            raise ErrorPublicacion(f"falta {ruta} (correr pytest -m calidad)")
        archivos[nombre] = ruta.read_bytes()
    reporte = json.loads(archivos[f"calidad_{sesion}.json"])
    for gid, g in sorted(reporte["grabaciones"].items()):
        p = g.get("principal")
        if g["estado"] != "valida" or not p:
            continue
        hip = MODULO / p["hipotesis"] / "diarization.json"
        if not hip.is_file():
            raise ErrorPublicacion(f"{gid}: falta la hipótesis {hip}")
        datos = hip.read_bytes()
        if hashlib.sha256(datos).hexdigest() != p["diarization_sha256"]:
            raise ErrorPublicacion(f"{gid}: diarization.json no coincide con el diarization_sha256 del reporte")
        archivos[f"hipotesis_{sesion}/{gid}.json"] = datos
    for nombre, datos in archivos.items():
        if RUTA_ABSOLUTA.search(datos.decode("utf-8")):
            raise ErrorPublicacion(f"{nombre}: contiene una ruta absoluta; no se publica")
    return archivos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publica los resultados de calidad en evaluacion/resultados/.")
    parser.add_argument("--sesion", default="S26")
    args = parser.parse_args(argv)
    try:
        archivos = preparar(args.sesion)
    except ErrorPublicacion as e:
        print(f"FALLA: {e}", file=sys.stderr)
        return 1
    for nombre, datos in archivos.items():
        destino = DESTINO / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
    print(f"OK  {len(archivos)} archivos en {DESTINO.relative_to(MODULO).as_posix()}/ "
          f"({sum(len(d) for d in archivos.values()) // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
