"""Evaluación independiente del juez con reuniones humanas alternadas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .archivos import PLANILLAS, SALIDA, carpeta_ejecucion, guardar_csv, guardar_json, leer_csv, sha256
from .juez import Juez, agregar, cargar_ejemplos
from .metricas import metricas_juez
from .reporte import escribir_markdown

VOTOS = ("reunion", "condicion", "item_id", "ejemplo_reunion", "resultado", "cita", "observaciones", "estado")
AGREGADOS = ("reunion", "tipo", "item_id", "referencia", "recuperado_humano", "recuperado_juez")


def evaluar(planillas: Path, destino: Path, *, juez=None) -> None:
    ejemplos = cargar_ejemplos(planillas)
    juez = juez or Juez()
    destino.mkdir(parents=True, exist_ok=False)
    guardar_json(destino / "manifiesto.json", {
        "version_esquema": 1, "modelo": juez.identidad, "sha256_prompt": juez.prompt_sha,
        "ejemplos": {e.reunion: {"csv": e.sha_csv, "markdown": e.sha_markdown} for e in ejemplos},
    })
    votos, agregados = [], []
    for objetivo in ejemplos:
        objetivo.verificar()
        for item in leer_csv(objetivo.csv):
            resultados = []
            for ejemplo in ejemplos:
                if ejemplo.reunion == objetivo.reunion:
                    continue
                respuesta, aviso = juez.evaluar(item["referencia"], objetivo.minuta, ejemplo)
                resultados.append(respuesta.resultado)
                votos.append({"reunion": objetivo.reunion, "condicion": "", "item_id": item["item_id"],
                              "ejemplo_reunion": ejemplo.reunion, "resultado": respuesta.resultado,
                              "cita": json.dumps(respuesta.citas, ensure_ascii=False),
                              "observaciones": " ".join(filter(None, (respuesta.observaciones, aviso))),
                              "estado": "evaluado"})
            agregados.append({"reunion": objetivo.reunion, "tipo": item["tipo"], "item_id": item["item_id"],
                              "referencia": item["referencia"], "recuperado_humano": item["recuperado"],
                              "recuperado_juez": agregar(resultados)})
    for ejemplo in ejemplos:
        ejemplo.verificar()
    guardar_csv(destino / "predicciones.csv", VOTOS, votos)
    guardar_csv(destino / "agregados.csv", AGREGADOS, agregados)
    reporte = {"version_esquema": 1, "tipo": "evaluacion_juez", "global": metricas_juez(agregados),
               "reuniones": {e.reunion: metricas_juez([f for f in agregados if f["reunion"] == e.reunion])
                             for e in ejemplos},
               "categorias": {tipo: metricas_juez([f for f in agregados if f["tipo"] == tipo])
                              for tipo in sorted({f["tipo"] for f in agregados})},
               "archivos": {"predicciones.csv": sha256(destino / "predicciones.csv"),
                            "agregados.csv": sha256(destino / "agregados.csv")},
               "limitaciones": ["Las etiquetas humanas y el juez no prueban calidad en reuniones extensas."]}
    guardar_json(destino / "reporte.json", reporte)
    escribir_markdown(destino / "reporte.json", destino / "reporte.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluación independiente del juez local.")
    parser.add_argument("--ejecucion", required=True)
    parser.add_argument("--salida", type=Path, default=SALIDA)
    parser.add_argument("--planillas", type=Path, default=PLANILLAS)
    args = parser.parse_args(argv)
    try:
        evaluar(args.planillas, carpeta_ejecucion(args.salida, "evaluacion_juez", args.ejecucion))
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Error en evaluación del juez: {exc}", file=sys.stderr)
        return 1
    print("Evaluación del juez finalizada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
