"""Prueba de recuperación ante interrupciones (§2.1 «Error del sistema», criterio de §2.3).

Graba con la captura de la aplicación, la cierra con SIGKILL a los `segundos` de empezar y mide lo perdido como el
tiempo grabado hasta el corte menos la duración del WAV que queda. Después comprueba que el WAV es válido, que
`consultar_grabaciones_interrumpidas` lo lista y, opcionalmente, que el pipeline lo procesa.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

LIMITE_PERDIDA_S = 5.0  # §2.3


def medir_corte(comando: list[str], carpeta: Path, segundos: float, *, espera_inicio_s: float = 30.0) -> dict:
    """Lanza `comando` (que graba en `carpeta`), espera su .json «grabando», lo corta con SIGKILL y mide."""
    from src.captura.recuperacion import consultar_grabaciones_interrumpidas
    from src.ingesta.audio import verificar_wav

    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    previos = set(carpeta.glob("*.json"))
    proceso = subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    t0, reporte, limite = None, None, time.monotonic() + espera_inicio_s
    while time.monotonic() < limite and proceso.poll() is None:
        nuevos = [p for p in carpeta.glob("*.json") if p not in previos]
        if nuevos:
            t0, reporte = time.monotonic(), nuevos[0]
            break
        time.sleep(0.05)
    if t0 is None:
        proceso.kill()
        error = proceso.communicate(timeout=10)[1].decode(errors="replace")[-500:]
        return {"error": f"la captura no empezó a grabar en {espera_inicio_s} s: {error}", "cumple_perdida": False}
    time.sleep(max(0.0, t0 + segundos - time.monotonic()))
    os.kill(proceso.pid, signal.SIGKILL)
    t_corte = time.monotonic()
    proceso.wait(timeout=10)
    grabado = t_corte - t0
    audio = carpeta / json.loads(reporte.read_text(encoding="utf-8"))["archivo"]
    try:
        duracion, valido = verificar_wav(audio) / 16000, True
    except (OSError, ValueError, EOFError) as e:
        duracion, valido = 0.0, False
    listadas = {g.audio.resolve() for g in consultar_grabaciones_interrumpidas(carpeta)}
    perdido = grabado - duracion
    return {"archivo": audio.name, "grabado_s": round(grabado, 3), "duracion_wav_s": round(duracion, 3),
            "perdido_s": round(perdido, 3), "wav_valido": valido, "listada_como_interrumpida": audio.resolve() in listadas,
            "cumple_perdida": valido and perdido <= LIMITE_PERDIDA_S, "senal": "SIGKILL",
            "medicion": "inicio = aparición del .json «grabando» (sondeo cada 50 ms); corte = envío de SIGKILL"}


def prueba_de_recuperacion(c: dict, segundos: float) -> int:
    """Prueba real con la captura de la aplicación (micrófono y audio del sistema detectados por PipeWire)."""
    from .__main__ import RAIZ, comando

    carpeta = c["corridas"] / "recuperacion" / "grabaciones"
    print(f"Grabando {segundos:.0f} s con la captura de la aplicación; después se corta con SIGKILL…", flush=True)
    r = medir_corte([sys.executable, "-m", "src.captura.captura", "--salida", str(carpeta)], carpeta, segundos)
    if not r.get("error") and r["wav_valido"]:
        salida = c["corridas"] / "recuperacion" / "proceso"
        print("Procesando el archivo recuperado con el pipeline…", flush=True)
        with open(c["corridas"] / "recuperacion" / "proceso.log", "w", encoding="utf-8") as log:
            codigo = subprocess.run(comando(c, "recuperacion", [carpeta / r["archivo"]], salida), cwd=RAIZ,
                                    stdout=log, stderr=subprocess.STDOUT).returncode
        estado = json.loads((salida / "workflow.json").read_text(encoding="utf-8")).get("estado") \
            if (salida / "workflow.json").is_file() else None
        r["procesable"] = codigo == 0 and estado == "completado"
        r["proceso"] = {"codigo": codigo, "estado": estado}
    r["cumple"] = bool(r.get("cumple_perdida") and r.get("procesable") and r.get("listada_como_interrumpida"))
    r["pendiente_manual"] = "que la aplicación, al reiniciar, la liste y ofrezca procesarla (protocolo del tercero)"
    c["resultados"].mkdir(parents=True, exist_ok=True)
    (c["resultados"] / "recuperacion.json").write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n",
                                                       encoding="utf-8")
    for k in ("grabado_s", "duracion_wav_s", "perdido_s", "wav_valido", "listada_como_interrumpida", "procesable", "cumple"):
        print(f"  {k}: {r.get(k)}")
    if r.get("error"):
        print(r["error"], file=sys.stderr)
    return 0 if r["cumple"] else 1
