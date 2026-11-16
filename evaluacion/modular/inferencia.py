"""Inferencia sobre la muestra congelada (requisito «Inferencia sobre la muestra verificada», D9 y D15).

Cada elemento se corre con el comando de su etapa, en un proceso aparte (libera la GPU al terminar):
- clip: `python -m src.stt` (Etapa 3);
- tarea de Figshare: `python -m src.pipeline ejecutar`, la cadena real 2→3→4→5;
- reunión de AMI: `python -m src.minutas` (Etapa 5) sobre su `transcription.json` traducido.
Al terminar bien se escribe `inferencia.json`; una salida con el mismo insumo, la misma configuración y todos sus
archivos se reutiliza salvo `rehacer`.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .muestra import verificar_muestra

RAIZ = Path(__file__).resolve().parents[2]
ARCHIVOS_ESPERADOS = {
    "clip": ("asr.json",),
    "figshare": ("diarization.json", "asr.json", "transcription.json", "minutes.json", "ejecucion_minutas.json"),
    "ami": ("minutes.json", "ejecucion_minutas.json"),
}


class MuestraAlterada(Exception):
    """La muestra no coincide con su manifiesto: no se infiere nada."""


def _tipo(elemento: dict) -> str:
    return elemento["fuente"] if elemento["fuente"] in ("figshare", "ami") else "clip"


def _entrada(elemento: dict, datos: Path) -> Path:
    if elemento["fuente"] == "ami":
        reunion = elemento.get("reunion") or elemento["id"].split("-", 1)[1]
        return datos / "ami" / reunion / "transcription.json"
    return datos / next(r for r in elemento["archivos"] if r.endswith("audio.wav"))


def _comando(elemento: dict, entrada: Path, carpeta: Path, modelos: dict) -> list[str]:
    py, secciones = sys.executable, ",".join(modelos["secciones"])
    tipo = _tipo(elemento)
    if tipo == "clip":
        return [py, "-m", "src.stt", str(entrada), "-o", str(carpeta / "asr.json"), "--model", modelos["modelo_stt"],
                "--device", modelos["dispositivo"]]
    if tipo == "figshare":
        return [py, "-m", "src.pipeline", "ejecutar", str(entrada), "--salida", str(carpeta),
                "--modelo-stt", modelos["modelo_stt"], "--dispositivo-stt", modelos["dispositivo"],
                "--dispositivo-diarizacion", modelos["dispositivo"], "--modelo", modelos["modelo_minutas"],
                "--secciones", secciones]
    return [py, "-m", "src.minutas", "--entrada", str(entrada), "--salida", str(carpeta),
            "--modelo", modelos["modelo_minutas"], "--secciones", secciones, "--sobrescribir"]


def ejecutar_proceso(comando: list[str], carpeta: Path, fuente: str) -> int:
    carpeta.mkdir(parents=True, exist_ok=True)
    with open(carpeta / "inferencia.log", "w", encoding="utf-8") as log:
        return subprocess.run(comando, cwd=RAIZ, stdout=log, stderr=subprocess.STDOUT).returncode


def _sin_rutas(comando: list[str], config) -> list[str]:
    reemplazos = [(str(config.salida), "<datos>"), (str(config.inferencia), "<inferencia>"), (sys.executable, "python")]
    salida = []
    for parte in comando:
        for ruta, marca in reemplazos:
            parte = parte.replace(ruta, marca)
        salida.append(parte)
    return salida


def _vigente(carpeta: Path, tipo: str, sha: str, modelos: dict) -> bool:
    try:
        registro = json.loads((carpeta / "inferencia.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (registro.get("codigo") == 0 and registro.get("entrada_sha256") == sha
            and registro.get("configuracion") == modelos
            and all((carpeta / n).is_file() for n in ARCHIVOS_ESPERADOS[tipo]))


def inferir(config, *, rehacer: bool = False, ejecutar=ejecutar_proceso, avisar=lambda *_: None) -> dict:
    problemas = verificar_muestra(config.manifiesto, config.salida)
    if problemas:
        raise MuestraAlterada("La muestra no coincide con su manifiesto:\n" + "\n".join(f"- {p}" for p in problemas))
    elementos = sorted(json.loads(config.manifiesto.read_text(encoding="utf-8"))["contenido"]["elementos"],
                       key=lambda e: e["id"])
    resumen, fallidos = {"ejecutados": 0, "reutilizados": 0}, []
    for i, elemento in enumerate(elementos, start=1):
        tipo, carpeta = _tipo(elemento), Path(config.inferencia) / elemento["id"]
        entrada = _entrada(elemento, Path(config.salida))
        sha = hashlib.sha256(entrada.read_bytes()).hexdigest()
        if not rehacer and _vigente(carpeta, tipo, sha, config.modelos):
            resumen["reutilizados"] += 1
            continue
        if rehacer and carpeta.exists():
            shutil.rmtree(carpeta)
        (carpeta / "inferencia.json").unlink(missing_ok=True)
        comando = _comando(elemento, entrada, carpeta, config.modelos)
        avisar(f"[{i}/{len(elementos)}] {elemento['id']}…")
        inicio = time.time()
        codigo = ejecutar(comando, carpeta, tipo)
        resumen["ejecutados"] += 1
        faltan = [n for n in ARCHIVOS_ESPERADOS[tipo] if not (carpeta / n).is_file()]
        if codigo != 0 or faltan:
            fallidos.append(elemento["id"])
            avisar(f"    falló (código {codigo}; faltan {', '.join(faltan) or 'nada'}); ver {carpeta / 'inferencia.log'}")
            continue
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "inferencia.json").write_text(json.dumps({
            "elemento": elemento["id"], "entrada_sha256": sha, "configuracion": config.modelos,
            "comando": _sin_rutas(comando, config), "segundos": round(time.time() - inicio, 1), "codigo": codigo,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if fallidos:
        resumen["fallidos"] = fallidos
    return resumen
