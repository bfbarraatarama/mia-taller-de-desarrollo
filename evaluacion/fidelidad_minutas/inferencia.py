"""Ejecución pareada sobre la misma transcripción y configuración."""

from __future__ import annotations

import platform
from pathlib import Path

import httpx

from src.minutas import ConfiguracionMinutas, generar_minuta
from src.minutas.experimento import ExperimentoMinutas
from src.minutas.generacion import huella_experimento
from src.minutas.proveedores import resolver_destino

from .archivos import guardar_json, sha256
from .fragmentacion import partir, serializar
from .preparacion import verificar


def modelo_local(nombre: str, *, requerido: bool = True) -> dict | None:
    destino = resolver_destino("qwen2.5-7b")
    if destino.tipo != "ollama_local":
        raise ValueError("La evaluación requiere un servidor Ollama local.")
    try:
        with httpx.Client(base_url=destino.host, trust_env=False, follow_redirects=False, timeout=30) as cliente:
            respuesta = cliente.get("/api/tags")
            respuesta.raise_for_status()
            modelos = respuesta.json()["models"]
            modelo = next((m for m in modelos if m.get("name") == nombre), None)
            if modelo is None and not requerido:
                return None
            if modelo is None or not modelo.get("digest"):
                raise RuntimeError(f"El modelo local {nombre} no está instalado.")
            version = cliente.get("/api/version")
            version.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"No se pudo consultar Ollama local ({type(exc).__name__}).") from None
    return {"nombre": nombre, "digest": modelo["digest"], "ollama": version.json()["version"],
            "hardware": platform.platform()}


def inferir(carpeta: Path, *, cliente=None, identidad: dict | None = None) -> None:
    muestra = carpeta / "muestra"
    manifiesto = verificar(muestra)
    config = ConfiguracionMinutas(secciones=("resumen", "decisiones", "problemas", "acciones"))
    identidad = identidad or modelo_local("qwen2.5:7b")
    if identidad is None:
        raise RuntimeError("No se pudo identificar el modelo de minutas.")
    huella = huella_experimento(config)
    destino = carpeta / "inferencia"
    destino.mkdir(exist_ok=False)
    for reunion in manifiesto["reuniones"]:
        nombre = reunion["reunion"]
        transcripcion = muestra / "ami" / nombre / "transcription.json"
        entrada_sha = sha256(transcripcion)
        base = ExperimentoMinutas(entrada_sha, huella)
        ruta = destino / nombre
        generar_minuta(transcripcion, ruta / "baseline", configuracion=config, cliente=cliente, experimento=base)
        if not base.bloques:
            raise ValueError(f"No hay bloques de extracción en {nombre}.")
        guardar_json(ruta / "baseline" / "traza.json",
                     {"version": 1, "sha256_entrada": entrada_sha, "sha256_configuracion": huella,
                      "bloques": serializar(base.bloques)})
        plan = partir(tuple(base.bloques))
        guardar_json(ruta / "plan_forzado.json", {"version": 1, "sha256_entrada": entrada_sha,
                     "sha256_configuracion": huella, "bloques": serializar(plan)})
        if cliente is None:
            actual = modelo_local("qwen2.5:7b")
            if actual is None or actual["digest"] != identidad["digest"]:
                raise ValueError("El modelo de minutos cambió entre condiciones.")
        forzada = ExperimentoMinutas(entrada_sha, huella, tuple(base.bloques), plan)
        generar_minuta(transcripcion, ruta / "forzada", configuracion=config, cliente=cliente, experimento=forzada)
        if cliente is None:
            actual = modelo_local("qwen2.5:7b")
            if actual is None or actual["digest"] != identidad["digest"]:
                raise ValueError("El modelo de minutos cambió durante la extracción forzada.")
        padres = {b.padre_id for b in forzada.bloques}
        if len(forzada.bloques) <= len(base.bloques) or padres != {b.bloque_id for b in plan}:
            raise ValueError(f"La extracción forzada de {nombre} no cumple el plan.")
        guardar_json(ruta / "forzada" / "traza.json",
                     {"version": 1, "sha256_entrada": entrada_sha, "sha256_configuracion": huella,
                      "bloques": serializar(forzada.bloques)})
        archivos = {}
        for condicion in ("baseline", "forzada"):
            for archivo in ("minutes.json", "minutes.md", "ejecucion_minutas.json", "traza.json"):
                clave = f"{condicion}/{archivo}"
                archivos[clave] = sha256(ruta / clave)
        archivos["plan_forzado.json"] = sha256(ruta / "plan_forzado.json")
        guardar_json(ruta / "comparacion.json", {
            "version_esquema": 1, "reunion": nombre, "sha256_entrada": entrada_sha,
            "sha256_configuracion": huella, "baseline_bloques": len(base.bloques),
            "forzada_bloques": len(forzada.bloques), "estado": "completado",
            "modelo": identidad, "archivos": archivos,
        })
