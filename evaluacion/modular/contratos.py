"""Contratos de los cuatro módulos sobre las salidas guardadas (criterio «Funcionamiento modular» de §2.3).

Cada salida se valida con el validador de su etapa, sin cargar modelos:
- diarización: `validar_diarizacion` de `src/diarizacion/contrato.py`;
- transcripción: `validate_asr_contract` de `src/stt/contrato.py`;
- asociación: `validar_transcripcion` de `src/asociacion/contrato.py` y la lectura de la Etapa 5 (`leer_transcripcion`);
- minutas: el modelo de `src/minutas/contratos.py` para sus secciones y `validar_evidencias`.
Una salida que falta se informa como faltante, no como violación.
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

MODULOS = ("diarizacion", "stt", "asociacion", "minutas")


class Faltante(Exception):
    """Falta una salida guardada."""


def _leer(ruta: Path):
    if not ruta.is_file():
        raise Faltante(ruta)
    return json.loads(ruta.read_text(encoding="utf-8"))


def _duracion(datos: Path, elemento: dict) -> float | None:
    for relativa in elemento["archivos"]:
        if relativa.endswith("audio.wav"):
            with wave.open(str(datos / relativa), "rb") as w:
                return w.getnframes() / w.getframerate()
    return None


def _transcripcion_de(elemento: dict, datos: Path, inferencia: Path) -> Path:
    if elemento["fuente"] == "ami":
        reunion = elemento.get("reunion") or elemento["id"].split("-", 1)[1]
        return datos / "ami" / reunion / "transcription.json"
    return inferencia / elemento["id"] / "transcription.json"


def _violaciones(modulo: str, elemento: dict, datos: Path, inferencia: Path) -> tuple[str, list[str]]:
    """(archivo evaluado, reglas incumplidas); lanza Faltante si falta una salida."""
    carpeta = inferencia / elemento["id"]
    duracion = _duracion(datos, elemento)
    if modulo == "stt":
        from src.stt.contrato import validate_asr_contract

        try:
            validate_asr_contract(_leer(carpeta / "asr.json"), duracion)
        except ValueError as e:
            return "asr.json", [str(e)]
        return "asr.json", []
    if modulo == "diarizacion":
        from src.diarizacion.contrato import validar_diarizacion

        return "diarization.json", validar_diarizacion(_leer(carpeta / "diarization.json"), duracion)
    if modulo == "asociacion":
        from src.asociacion.contrato import validar_transcripcion
        from src.minutas.entrada import leer_transcripcion

        etiquetas = {s["speaker"] for s in _leer(carpeta / "diarization.json")["segments"]}
        reglas = validar_transcripcion(_leer(carpeta / "transcription.json"), duracion, etiquetas)
        try:
            leer_transcripcion(carpeta / "transcription.json")
        except Exception as e:  # la Etapa 5 no puede leerla
            reglas.append(f"lectura de la Etapa 5: {e}")
        return "transcription.json", reglas
    from src.minutas.contratos import modelo_minuta, validar_evidencias
    from src.minutas.entrada import leer_transcripcion

    secciones = tuple(_leer(carpeta / "ejecucion_minutas.json")["secciones"])
    texto = (carpeta / "minutes.json")
    if not texto.is_file():
        raise Faltante(texto)
    try:
        minuta = modelo_minuta(secciones).model_validate_json(texto.read_text(encoding="utf-8"))
        intervenciones, _ = leer_transcripcion(_transcripcion_de(elemento, datos, inferencia))
        validar_evidencias(minuta, intervenciones)
    except ValueError as e:  # incluye ValidationError de pydantic
        return "minutes.json", [str(e).splitlines()[0] if str(e) else type(e).__name__]
    return "minutes.json", []


def evaluar_contratos(manifiesto: Path, datos: Path, inferencia: Path) -> dict:
    m = json.loads(Path(manifiesto).read_text(encoding="utf-8"))
    datos, inferencia = Path(datos), Path(inferencia)
    modulos = {mod: {"validas": 0, "total": 0, "faltantes": [], "violaciones": []} for mod in MODULOS}
    for elemento in m["contenido"]["elementos"]:
        for modulo in elemento["modulos"]:
            r = modulos[modulo]
            r["total"] += 1
            try:
                archivo, reglas = _violaciones(modulo, elemento, datos, inferencia)
            except Faltante as f:
                r["faltantes"].append(Path(str(f.args[0])).relative_to(inferencia).as_posix()
                                      if str(f.args[0]).startswith(str(inferencia)) else Path(str(f.args[0])).name)
                continue
            relativa = f"{elemento['id']}/{archivo}"
            if reglas:
                r["violaciones"] += [{"archivo": relativa, "regla": regla} for regla in reglas]
            else:
                r["validas"] += 1
    for r in modulos.values():
        r["porcentaje"] = round(100 * r["validas"] / r["total"], 1) if r["total"] else None
    cumple = all(r["total"] and r["validas"] == r["total"] for r in modulos.values())
    return {"criterio": "Funcionamiento modular (§2.3): 4/4 módulos con el 100 % de sus salidas dentro del contrato",
            "cumple": cumple, "modulos_al_100": sum(r["total"] > 0 and r["validas"] == r["total"]
                                                     for r in modulos.values()),
            "contenido_sha256_muestra": m["contenido_sha256"], "modulos": modulos}
