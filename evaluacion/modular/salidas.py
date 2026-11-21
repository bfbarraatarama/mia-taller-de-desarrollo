"""Salidas de los módulos versionadas (`resultados/salidas/`), para recalcular contratos y métricas sin GPU.

Se publican solo los JSON y la minuta en Markdown que usa `evaluar`, más el `inferencia.json` de cada elemento
(insumo, configuración, código y comando sin rutas locales). No se publica audio ni registros de ejecución.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ARCHIVOS = ("asr.json", "diarization.json", "transcription.json", "minutes.json", "minutes.md",
            "ejecucion_minutas.json", "inferencia.json")


def publicar_salidas(inferencia: Path, destino: Path) -> int:
    """Copia las salidas de `inferencia` a `destino`, reemplazándolo entero; devuelve la cantidad de archivos."""
    inferencia, destino = Path(inferencia), Path(destino)
    nuevo = destino.with_name(destino.name + ".publicando")
    shutil.rmtree(nuevo, ignore_errors=True)
    copiados = 0
    for carpeta in sorted(p for p in inferencia.iterdir() if p.is_dir()):
        for nombre in ARCHIVOS:
            origen = carpeta / nombre
            if origen.is_file():
                (nuevo / carpeta.name).mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origen, nuevo / carpeta.name / nombre)
                copiados += 1
    nuevo.mkdir(parents=True, exist_ok=True)
    anterior = destino.with_name(destino.name + ".anterior")
    shutil.rmtree(anterior, ignore_errors=True)
    if destino.exists():
        os.replace(destino, anterior)
    os.replace(nuevo, destino)
    shutil.rmtree(anterior, ignore_errors=True)
    return copiados
