"""Inferencia sobre la muestra congelada (requisito «Inferencia sobre la muestra verificada», D9 y D15).

Cada elemento se corre con el comando de su etapa, en un proceso aparte (libera la GPU al terminar):
- clip: `python -m src.stt` (Etapa 3);
- tarea de Figshare: `python -m src.pipeline ejecutar`, la cadena real 2→3→4→5;
- reunión de AMI: `python -m src.minutas` (Etapa 5) sobre su `transcription.json` traducido.
Al terminar bien se escribe `inferencia.json`; una salida con el mismo insumo, la misma configuración, el mismo
código de sus etapas (`huella_codigo`) y todos sus archivos se reutiliza salvo `rehacer`. En Figshare, el pipeline
vuelve a correr en la misma carpeta y reutiliza por su cuenta las etapas que siguen vigentes.
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


# Código del que depende cada tipo de elemento: si cambia, su salida deja de ser vigente.
CODIGO = {
    "clip": ("src/stt", "src/tiempos.py"),
    "figshare": ("src/ingesta", "src/diarizacion", "src/stt", "src/asociacion", "src/minutas", "src/pipeline",
                 "src/tiempos.py", "src/rutas.py"),
    "ami": ("src/minutas",),
}


def huella_codigo(tipo: str) -> str:
    """SHA-256 del código (y los prompts) de las etapas que usa un tipo de elemento."""
    h = hashlib.sha256()
    for relativa in CODIGO[tipo]:
        ruta = RAIZ / relativa
        archivos = [ruta] if ruta.is_file() else sorted(
            p for p in ruta.rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".json") and "__pycache__" not in p.parts)
        for archivo in archivos:
            h.update(archivo.relative_to(RAIZ).as_posix().encode() + b"\0" + archivo.read_bytes() + b"\0")
    return h.hexdigest()


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


def _hashes_salidas(carpeta: Path, tipo: str) -> dict[str, str] | None:
    """SHA-256 de cada archivo esperado; None si falta alguno."""
    if not all((carpeta / n).is_file() for n in ARCHIVOS_ESPERADOS[tipo]):
        return None
    return {n: hashlib.sha256((carpeta / n).read_bytes()).hexdigest() for n in ARCHIVOS_ESPERADOS[tipo]}


def _pipeline_completado(carpeta: Path) -> bool:
    try:
        return json.loads((carpeta / "workflow.json").read_text(encoding="utf-8")).get("estado") == "completado"
    except (OSError, ValueError):
        return False


def _vigente(carpeta: Path, tipo: str, sha: str, modelos: dict, codigo: str) -> bool:
    """Mismo insumo, configuración y código; salidas intactas (SHA-256 del registro) y, en Figshare, pipeline completo."""
    try:
        registro = json.loads((carpeta / "inferencia.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (registro.get("codigo") == 0 and registro.get("entrada_sha256") == sha
            and registro.get("configuracion") == modelos and registro.get("codigo_sha256") == codigo
            and registro.get("salidas_sha256") is not None
            and registro["salidas_sha256"] == _hashes_salidas(carpeta, tipo)
            and (tipo != "figshare" or _pipeline_completado(carpeta)))


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
        huella = huella_codigo(tipo)
        if not rehacer and _vigente(carpeta, tipo, sha, config.modelos, huella):
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
        if tipo == "figshare" and not faltan and not _pipeline_completado(carpeta):
            faltan.append("workflow.json con estado «completado»")
        if codigo != 0 or faltan:
            fallidos.append(elemento["id"])
            avisar(f"    falló (código {codigo}; faltan {', '.join(faltan) or 'nada'}); ver {carpeta / 'inferencia.log'}")
            continue
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / "inferencia.json").write_text(json.dumps({
            "elemento": elemento["id"], "entrada_sha256": sha, "configuracion": config.modelos, "codigo_sha256": huella,
            "salidas_sha256": _hashes_salidas(carpeta, tipo),
            "comando": _sin_rutas(comando, config), "segundos": round(time.time() - inicio, 1), "codigo": codigo,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if fallidos:
        resumen["fallidos"] = fallidos
    return resumen
