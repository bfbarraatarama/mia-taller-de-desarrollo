"""Juicios, persistencia y comparación de las dos condiciones."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .archivos import guardar_csv, guardar_json, leer_csv, leer_json, sha256, verificar_archivos
from .evaluar_juez import VOTOS
from .juez import Juez, agregar, cargar_ejemplos
from .metricas import comparar
from .preparacion import verificar
from .reporte import escribir_markdown

COLUMNAS = ("reunion", "condicion", "tipo", "item_id", "referencia", "referencia_original", "estado",
            "recuperado", "cita", "observaciones", "sha256_referencia", "sha256_minuta")


def juzgar(carpeta: Path, planillas: Path, *, juez=None) -> None:
    muestra = carpeta / "muestra"
    manifiesto = verificar(muestra)
    ejemplos = cargar_ejemplos(planillas)
    juez = juez or Juez()
    destino = carpeta / "evaluacion"
    destino.mkdir(exist_ok=False)
    archivos = {}
    for reunion in manifiesto["reuniones"]:
        nombre = reunion["reunion"]
        referencia = muestra / "ami" / nombre / "referencia_minuta.json"
        items = leer_json(referencia)["items"]
        ruta = carpeta / "inferencia" / nombre
        comparacion = leer_json(ruta / "comparacion.json")
        if comparacion["estado"] != "completado" or comparacion["sha256_entrada"] != sha256(
                muestra / "ami" / nombre / "transcription.json"):
            raise ValueError(f"Comparación inválida para {nombre}.")
        verificar_archivos(ruta, comparacion["archivos"])
        if comparacion["modelo"]["digest"] == juez.identidad["digest"]:
            raise ValueError("El generador y el juez no pueden usar el mismo modelo.")
        for condicion in ("baseline", "forzada"):
            minuto = ruta / condicion / "minutes.md"
            texto = minuto.read_text(encoding="utf-8")
            filas, votos = [], []
            for item in items:
                respuestas = []
                for ejemplo in ejemplos:
                    respuesta, aviso = juez.evaluar(item["texto"], texto, ejemplo)
                    respuestas.append(respuesta)
                    votos.append({"reunion": nombre, "condicion": condicion, "item_id": item["item_id"],
                                  "ejemplo_reunion": ejemplo.reunion, "resultado": respuesta.resultado,
                                  "cita": json.dumps(respuesta.citas, ensure_ascii=False),
                                  "observaciones": " ".join(filter(None, (respuesta.observaciones, aviso))),
                                  "estado": "evaluado"})
                resultado = agregar([r.resultado for r in respuestas])
                citas = [c for r in respuestas if r.resultado == resultado == "sí" for c in r.citas]
                observaciones = " | ".join(r.observaciones for r in respuestas if r.observaciones)
                if resultado == "incierto" and len({r.resultado for r in respuestas}) == 3:
                    observaciones = " | ".join(filter(None, (observaciones, "Empate en los votos del juez.")))
                filas.append({"reunion": nombre, "condicion": condicion, "tipo": item["tipo"],
                              "item_id": item["item_id"], "referencia": item["texto"],
                              "referencia_original": item["texto_original"],
                              "estado": "evaluado" if resultado in ("sí", "no") else resultado,
                              "recuperado": resultado if resultado in ("sí", "no") else "",
                              "cita": json.dumps(citas, ensure_ascii=False), "observaciones": observaciones,
                              "sha256_referencia": sha256(referencia), "sha256_minuta": sha256(minuto)})
            verificar_archivos(ruta, comparacion["archivos"])
            guardar_csv(destino / nombre / f"{condicion}.csv", COLUMNAS, filas)
            guardar_csv(destino / nombre / f"{condicion}_predicciones.csv", VOTOS, votos)
            for archivo in (f"{condicion}.csv", f"{condicion}_predicciones.csv"):
                clave = f"{nombre}/{archivo}"
                archivos[clave] = sha256(destino / clave)
    for ejemplo in ejemplos:
        ejemplo.verificar()
    guardar_json(destino / "manifiesto.json", {
        "version_esquema": 1, "modelo": juez.identidad, "sha256_prompt": juez.prompt_sha,
        "ejemplos": {e.reunion: {
            "csv": os.path.relpath(e.csv, carpeta), "sha256_csv": e.sha_csv,
            "markdown": os.path.relpath(e.markdown, carpeta), "sha256_markdown": e.sha_markdown,
        } for e in ejemplos},
        "archivos": archivos,
    })


def reportar(carpeta: Path) -> None:
    manifiesto = verificar(carpeta / "muestra")
    evaluacion = leer_json(carpeta / "evaluacion" / "manifiesto.json")
    verificar_archivos(carpeta / "evaluacion", evaluacion["archivos"])
    for ejemplo in evaluacion["ejemplos"].values():
        if (sha256(carpeta / ejemplo["csv"]) != ejemplo["sha256_csv"]
                or sha256(carpeta / ejemplo["markdown"]) != ejemplo["sha256_markdown"]):
            raise ValueError("Un par de ejemplos fue alterado después del juicio.")
    resultados = {}
    hashes = {}
    for reunion in manifiesto["reuniones"]:
        nombre = reunion["reunion"]
        ruta = carpeta / "inferencia" / nombre
        comparacion = leer_json(ruta / "comparacion.json")
        verificar_archivos(ruta, comparacion["archivos"])
        if comparacion["estado"] != "completado" or comparacion["forzada_bloques"] <= comparacion["baseline_bloques"]:
            raise ValueError(f"Comparación de bloques inválida: {nombre}.")
        referencia = carpeta / "muestra" / "ami" / nombre / "referencia_minuta.json"
        items = leer_json(referencia)["items"]
        por_id = {i["item_id"]: i for i in items}
        condiciones = []
        for condicion in ("baseline", "forzada"):
            csv = carpeta / "evaluacion" / nombre / f"{condicion}.csv"
            filas = leer_csv(csv)
            esperados = {i["item_id"] for i in items}
            if len(filas) != len(esperados) or {f["item_id"] for f in filas} != esperados:
                raise ValueError(f"Faltan ítems en {csv}.")
            for f in filas:
                if (f["reunion"] != nombre or f["condicion"] != condicion
                        or f["referencia"] != por_id[f["item_id"]]["texto"]
                        or f["referencia_original"] != por_id[f["item_id"]]["texto_original"]
                        or f["tipo"] != por_id[f["item_id"]]["tipo"]
                        or f["sha256_referencia"] != sha256(referencia)
                        or f["sha256_minuta"] != sha256(ruta / condicion / "minutes.md")
                        or f["estado"] not in ("evaluado", "incierto", "no_evaluable")
                        or (f["estado"] == "evaluado" and f["recuperado"] not in ("sí", "no"))
                        or (f["estado"] != "evaluado" and f["recuperado"])):
                    raise ValueError(f"Evaluación inválida en {csv}.")
            condiciones.append(filas)
            hashes[str(csv.relative_to(carpeta))] = sha256(csv)
        resultados[nombre] = comparar(*condiciones)
    reporte = {"version_esquema": 1, "tipo": "evaluacion_minutas", "reuniones": resultados,
               "archivos": hashes, "limitaciones": [
                   "Recall estimado por un juez automático; las citas no están verificadas.",
                   "La diferencia puede reflejar variabilidad del modelo, contexto y consolidación."]}
    guardar_json(carpeta / "reporte.json", reporte)
    escribir_markdown(carpeta / "reporte.json", carpeta / "reporte.md")
