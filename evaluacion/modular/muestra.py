"""Muestra congelada y su manifiesto (requisitos «Manifiesto verificable» y «Selección determinista»).

El manifiesto separa `contenido`, que depende solo de la semilla y de los originales y lleva su `contenido_sha256`,
de `ejecucion`, que registra fecha y versiones y cambia en cada corrida.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src.rar7z import listar, version_7zip

from .audio import leer_miembro, preparar_clip, preparar_tarea_figshare
from .seleccion import (inventario_ami, inventario_common_voice, inventario_openslr, seleccionar_clips,
                        seleccionar_reuniones, seleccionar_sesiones, sesiones_figshare)
from .traduccion import preparar_reunion_ami

VERSION = "0.1.0"
MODULOS_FIGSHARE = ["stt", "diarizacion", "asociacion", "minutas"]


def _sha(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def hash_contenido(contenido: dict) -> str:
    return _sha(json.dumps(contenido, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def construir_manifiesto(semilla: int, originales: dict[str, str], elementos: list[dict],
                         exclusiones: dict[str, str]) -> dict:
    contenido = {"version": VERSION, "semilla": semilla, "originales": dict(sorted(originales.items())),
                 "exclusiones": dict(sorted(exclusiones.items())),
                 "elementos": sorted(elementos, key=lambda e: e["id"])}
    return {"contenido": contenido, "contenido_sha256": hash_contenido(contenido)}


def verificar_muestra(manifiesto: Path, datos: Path) -> list[str]:
    """Compara cada archivo de la muestra con su SHA-256 del manifiesto, sin modificar nada."""
    m = json.loads(Path(manifiesto).read_text(encoding="utf-8"))
    problemas = []
    if hash_contenido(m["contenido"]) != m.get("contenido_sha256"):
        problemas.append(f"{Path(manifiesto).name}: el contenido no coincide con su contenido_sha256 "
                         "(el manifiesto se editó después de congelar la muestra)")
    for elemento in m["contenido"]["elementos"]:
        for relativa, esperado in sorted(elemento["archivos"].items()):
            ruta = Path(datos) / relativa
            if not ruta.is_file():
                problemas.append(f"{relativa}: falta en {datos}")
                continue
            encontrado = _sha(ruta.read_bytes())
            if encontrado != esperado:
                problemas.append(f"{relativa}: SHA-256 esperado {esperado}, encontrado {encontrado}")
    return problemas


def _tareas_figshare(rar_wavs: Path, rar_frases: Path, sesion: str) -> list[str]:
    """Números de tarea con los dos canales de audio y las dos anotaciones."""
    s = sesion.lower()
    wavs, frases = set(listar(rar_wavs)), set(listar(rar_frases))
    tareas = []
    for nombre in sorted(wavs):
        prefijo = f"wavs/{sesion}/{s}.objects."
        if nombre.startswith(prefijo) and nombre.endswith(".channel1.wav"):
            n = nombre[len(prefijo):-len(".channel1.wav")]
            requeridos = {f"wavs/{sesion}/{s}.objects.{n}.channel2.wav",
                          f"phrases/{sesion}/{s}.objects.{n}.channel1.phrases",
                          f"phrases/{sesion}/{s}.objects.{n}.channel2.phrases"}
            if requeridos <= wavs | frases:
                tareas.append(n)
    return tareas


def preparar_muestra(config, originales_sha: dict[str, str], *, traductor=None, avisar=print) -> dict:
    """Selecciona y prepara la muestra en una carpeta nueva y la publica en `config.salida`; devuelve el manifiesto."""
    cache, semilla = config.cache, config.semilla
    o = config.originales
    destino = Path(config.salida)
    nueva = destino.with_name(destino.name + ".preparando")
    shutil.rmtree(nueva, ignore_errors=True)
    elementos = []

    avisar("Seleccionando clips…")
    clips = seleccionar_clips(inventario_openslr(cache), inventario_common_voice(cache), semilla)
    for c in clips:
        clave = (o["common_voice"].clave if c.fuente == "common_voice"
                 else o["openslr_mujeres" if c.genero == "female" else "openslr_hombres"].clave)
        ident = f"clip-{c.fuente}-{Path(c.id).stem}"
        reg = preparar_clip(cache / clave, c.ruta, nueva / "clips" / ident)
        elementos.append({"id": ident, "fuente": c.fuente, "modulos": ["stt"], "hablante": c.hablante,
                          "genero": c.genero, "referencia": c.texto, "original": clave, "entrada": c.ruta,
                          "original_sha256": reg["original_sha256"], "transformacion": reg["transformacion"],
                          "archivos": {f"clips/{ident}/audio.wav": reg["sha256"]}})

    sesiones, exclusiones = seleccionar_sesiones(sesiones_figshare(cache), semilla)
    rar_wavs, rar_frases = cache / o["figshare_audio"].clave, cache / o["figshare_frases"].clave
    for sesion in sesiones:
        tareas = _tareas_figshare(rar_wavs, rar_frases, sesion)
        avisar(f"Preparando {sesion}: {len(tareas)} tareas…")
        for n in tareas:
            s, ident = sesion.lower(), f"figshare-{sesion}-{n}"
            canales = [f"wavs/{sesion}/{s}.objects.{n}.channel{k}.wav" for k in (1, 2)]
            frases = [f"phrases/{sesion}/{s}.objects.{n}.channel{k}.phrases" for k in (1, 2)]
            reg = preparar_tarea_figshare(rar_wavs, *canales, nueva / "figshare" / sesion / n)
            elementos.append({"id": ident, "fuente": "figshare", "sesion": sesion, "tarea": n,
                              "modulos": MODULOS_FIGSHARE, "original": o["figshare_audio"].clave,
                              "entradas": canales, "originales_sha256": reg["originales_sha256"],
                              "cuadros": reg["cuadros"], "transformacion": reg["transformacion"],
                              "referencia": {"original": o["figshare_frases"].clave,
                                             "entradas": {f: _sha(leer_miembro(rar_frases, f)) for f in frases}},
                              "archivos": {f"figshare/{sesion}/{n}/audio.wav": reg["sha256"]}})

    reuniones = seleccionar_reuniones(inventario_ami(), semilla)
    if reuniones and traductor is None:
        from .traduccion import Traductor
        traductor = Traductor()
    for r in reuniones:
        avisar(f"Traduciendo {r.id}…")
        reg = preparar_reunion_ami(r.id, nueva / "ami" / r.id, traductor)
        elementos.append({"id": f"ami-{r.id}", "fuente": "ami", "reunion": r.id, "serie": r.serie,
                          "duracion_s": r.duracion_s, "acciones": r.acciones, "modulos": ["minutas"],
                          "original": o["ami"].clave, "sintetico": True, "modelo": reg["modelo"],
                          "revision": reg["revision"], "parametros": reg["parametros"], "roles": reg["roles"],
                          "turnos": reg["turnos"], "descartados": reg["descartados"], "items": reg["items"],
                          "archivos": {f"ami/{r.id}/{k}": v for k, v in reg["archivos"].items()}})

    claves = {original.clave: originales_sha[nombre] for nombre, original in o.items()}
    manifiesto = construir_manifiesto(semilla, claves, elementos, exclusiones)

    anterior = destino.with_name(destino.name + ".anterior")
    shutil.rmtree(anterior, ignore_errors=True)
    if destino.exists():
        os.replace(destino, anterior)
    os.replace(nueva, destino)
    shutil.rmtree(anterior, ignore_errors=True)
    return manifiesto


def _primera_linea(comando: list[str]) -> str | None:
    try:
        return subprocess.run(comando, capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, IndexError):
        return None


def ejecucion(segundos: float) -> dict:
    import torch
    import transformers

    return {"fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "segundos": round(segundos, 1),
            "python": platform.python_version(), "plataforma": platform.platform(),
            "ffmpeg": _primera_linea(["ffmpeg", "-version"]), "7zip": version_7zip(),
            "torch": torch.__version__, "transformers": transformers.__version__}


def escribir_manifiesto(ruta: Path, manifiesto: dict, inicio: float) -> None:
    datos = {**manifiesto, "ejecucion": ejecucion(time.time() - inicio)}
    temporal = Path(ruta).with_suffix(".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)
