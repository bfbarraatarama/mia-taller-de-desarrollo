#!/usr/bin/env python3
"""Descarga las fuentes crudas del Hito 2 a hito-2/.cache/.

Alcance: producto en castellano, evaluado por módulo.

Uso (desde la raíz del repo):
    python3 -I hito-2/scripts/descargar_fuentes.py            # todo
    python3 -I hito-2/scripts/descargar_fuentes.py anotaciones
    python3 -I hito-2/scripts/descargar_fuentes.py audio
    python3 -I hito-2/scripts/descargar_fuentes.py castellano

Solo usa la biblioteca estándar. No vuelve a bajar lo que ya está. Lo
descargado NO se versiona (hito-2/.cache/ está en .gitignore).

Qué baja:
  anotaciones  AMI e ICSI (transcripción, hablantes y tiempos), los tiempos
               de VoxConverse y la partición de AMI que usa pyannote. 80 MB.
  audio        NO baja el audio completo (son más de 20 GB). Hace dos cosas:
               1. Índice: pide la cabecera del audio de cada reunión de AMI e
                  ICSI, para saber si existe, cuánto pesa y cuánto dura.
               2. Extractos: baja 30 segundos de 24 reuniones elegidas con
                  semilla fija. El servidor permite pedir solo un tramo.
  castellano   Audio con transcripción en castellano rioplatense, para el
               módulo de transcripción: OpenSLR 61, CORdeBA y Humyn LATAM.
               3,1 GB. Common Voice 26 rioplatense no se descarga: queda
               planteada como fuente candidata en el mapa de fuentes.
"""
from __future__ import annotations

import json
import random
import re
import struct
import sys
import urllib.error
import urllib.request
import wave
import zipfile
from pathlib import Path

SEMILLA = 20261010
CACHE = Path(__file__).resolve().parent.parent / ".cache"
EDI = "https://groups.inf.ed.ac.uk/ami"

ANOTACIONES = {
    "ami/ami_public_manual_1.6.2.zip": f"{EDI}/AMICorpusAnnotations/ami_public_manual_1.6.2.zip",
    "icsi/ICSI_plus_NXT.zip": f"{EDI}/ICSICorpusAnnotations/ICSI_plus_NXT.zip",
    "voxconverse/voxconverse-master.zip": "https://github.com/joonson/voxconverse/archive/refs/heads/master.zip",
    **{f"pyannote_ami/{p}.meetings.txt":
       f"https://raw.githubusercontent.com/pyannote/AMI-diarization-setup/main/lists/{p}.meetings.txt"
       for p in ("train", "dev", "test")},
}
AUDIO_AMI = EDI + "/AMICorpusMirror/amicorpus/{r}/audio/{r}.Mix-Headset.wav"
AUDIO_ICSI = EDI + "/ICSIsignals/NXT/{r}.interaction.wav"
AUDIO_VOX = {p: f"https://www.robots.ox.ac.uk/~vgg/data/voxconverse/data/voxconverse_{p}_wav.zip"
             for p in ("dev", "test")}

HF = "https://huggingface.co/datasets/{repo}/resolve/main/{path}"
CASTELLANO = {
    **{f"slr61/{f}": f"https://www.openslr.org/resources/61/{f}"
       for f in ("line_index_female.tsv", "line_index_male.tsv", "es_ar_male.zip", "es_ar_female.zip")},
    "cordeba/metadata.csv": HF.format(repo="marianbasti/cordeba", path="metadata.csv"),
    **{f"cordeba/CordeBA_{i:04d}.{e}": HF.format(repo="marianbasti/cordeba", path=f"data/CordeBA_{i:04d}.{e}")
       for i in range(1, 25) for e in (("wma",) if i == 16 else ("mp3",))},
    **{f"humyn/train-{i:05d}-of-00007.parquet":
       HF.format(repo="humyn-labs/LATAM-High-Fidelity-ASR", path=f"data/train-{i:05d}-of-00007.parquet")
       for i in range(7)},
}

# Cuántos extractos por grupo de reuniones (prefijo del identificador).
EXTRACTOS = {"ami": {"ES": 4, "IS": 4, "TS": 4, "EN": 2, "IB": 2}, "icsi": {"Bmr": 3, "Bro": 3, "Bed": 2}}
SEGUNDOS = 30


def pedir(url: str, rango: tuple[int, int] | None = None, metodo: str = "GET"):
    headers = {"User-Agent": "hito2-eda/1.0"}
    if rango:
        headers["Range"] = f"bytes={rango[0]}-{rango[1]}"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers, method=metodo), timeout=120)


def bajar(url: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and destino.stat().st_size:
        print(f"  ok (ya estaba)  {destino.name}")
        return
    tmp = destino.with_suffix(destino.suffix + ".part")
    with pedir(url) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(destino)
    print(f"  ok  {destino.name}  {destino.stat().st_size / 1e6:.1f} MB")


def anotaciones() -> None:
    print("[anotaciones]")
    for destino, url in ANOTACIONES.items():
        bajar(url, CACHE / destino)


def leer_cabecera_wav(datos: bytes) -> dict:
    """Formato y posición de los datos, leyendo los bloques RIFF del comienzo del archivo."""
    if datos[:4] != b"RIFF" or datos[8:12] != b"WAVE":
        raise ValueError("no es un WAV")
    pos, fmt = 12, None
    while pos + 8 <= len(datos):
        bloque, largo = datos[pos:pos + 4], struct.unpack("<I", datos[pos + 4:pos + 8])[0]
        if bloque == b"fmt ":
            _, canales, hz, _, alineacion, bits = struct.unpack("<HHIIHH", datos[pos + 8:pos + 24])
            fmt = {"canales": canales, "hz": hz, "bytes_por_cuadro": alineacion, "bits": bits}
        elif bloque == b"data":
            return {**(fmt or {}), "inicio_datos": pos + 8}
        pos += 8 + largo + (largo & 1)
    raise ValueError("no encontré el bloque de datos en los primeros bytes")


def reuniones() -> dict[str, list[str]]:
    """Identificadores de reunión, leídos de las anotaciones ya descargadas."""
    z = zipfile.ZipFile(CACHE / "ami/ami_public_manual_1.6.2.zip")
    ami = sorted(set(re.findall(r'observation="([^"]+)"', z.read("corpusResources/meetings.xml").decode("latin1"))))
    z = zipfile.ZipFile(CACHE / "icsi/ICSI_plus_NXT.zip")
    icsi = sorted({Path(n).name.split(".")[0] for n in z.namelist() if "/Segments/" in n and n.endswith(".xml")})
    return {"ami": ami, "icsi": icsi}


def indice_de_audio() -> dict:
    """Una fila por reunión: ¿existe el audio?, ¿cuánto pesa?, ¿qué formato y duración declara?"""
    destino = CACHE / "audio" / "indice.json"
    if destino.exists():
        print("  ok (ya estaba)  indice.json")
        return json.loads(destino.read_text())
    indice = {"ami": {}, "icsi": {}, "voxconverse": {}}
    for corpus, patron in (("ami", AUDIO_AMI), ("icsi", AUDIO_ICSI)):
        ids = reuniones()[corpus]
        for i, r in enumerate(ids, 1):
            url, fila = patron.format(r=r), {}
            try:
                with pedir(url, rango=(0, 4095)) as resp:
                    total = int(resp.headers["Content-Range"].rsplit("/", 1)[1])
                    cab = leer_cabecera_wav(resp.read())
                fila = {"url": url, "disponible": True, "bytes": total, **cab,
                        "duracion_s": (total - cab["inicio_datos"]) / cab["bytes_por_cuadro"] / cab["hz"]}
            except (urllib.error.URLError, ValueError, KeyError, struct.error) as e:
                fila = {"url": url, "disponible": False, "error": repr(e)[:160]}
            indice[corpus][r] = fila
            if i % 25 == 0 or i == len(ids):
                print(f"  {corpus}: {i}/{len(ids)}")
    for particion, url in AUDIO_VOX.items():
        try:
            with pedir(url, metodo="HEAD") as resp:
                indice["voxconverse"][particion] = {"url": url, "disponible": True,
                                                    "bytes": int(resp.headers["Content-Length"])}
        except urllib.error.URLError as e:
            indice["voxconverse"][particion] = {"url": url, "disponible": False, "error": repr(e)[:160]}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(indice, indent=1))
    print("  ok  indice.json")
    return indice


def extractos(indice: dict) -> None:
    """Baja 30 s de audio de 24 reuniones: elegidas por grupo, con semilla fija."""
    carpeta = CACHE / "audio" / "extractos"
    carpeta.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEMILLA)
    plan = []
    for corpus, cupos in EXTRACTOS.items():
        for prefijo, n in cupos.items():
            candidatas = sorted(r for r, f in indice[corpus].items()
                                if r.startswith(prefijo) and f.get("disponible") and f["duracion_s"] > 300)
            for r in rng.sample(candidatas, min(n, len(candidatas))):
                # El tramo empieza en algún punto entre el 20% y el 80% de la reunión.
                inicio = int(rng.uniform(0.2, 0.8) * (indice[corpus][r]["duracion_s"] - SEGUNDOS))
                plan.append({"corpus": corpus, "reunion": r, "inicio_s": inicio, "duracion_s": SEGUNDOS})
    for p in plan:
        f = indice[p["corpus"]][p["reunion"]]
        destino = carpeta / f"{p['reunion']}.wav"
        if not destino.exists():
            desde = f["inicio_datos"] + p["inicio_s"] * f["hz"] * f["bytes_por_cuadro"]
            hasta = desde + SEGUNDOS * f["hz"] * f["bytes_por_cuadro"] - 1
            with pedir(f["url"], rango=(desde, hasta)) as resp:
                crudo = resp.read()
            with wave.open(str(destino), "wb") as w:
                w.setnchannels(f["canales"])
                w.setsampwidth(f["bits"] // 8)
                w.setframerate(f["hz"])
                w.writeframes(crudo)
        print(f"  ok  {destino.name}  desde el segundo {p['inicio_s']}")
    (carpeta / "plan.json").write_text(json.dumps(plan, indent=1))


def audio() -> None:
    print("[audio]")
    extractos(indice_de_audio())


def castellano() -> None:
    print("[castellano]")
    for destino, url in CASTELLANO.items():
        bajar(url, CACHE / destino)


def main(argv: list[str]) -> int:
    pasos = {"anotaciones": anotaciones, "audio": audio, "castellano": castellano}
    try:
        for nombre in argv or list(pasos):
            pasos[nombre]()
    except (urllib.error.URLError, KeyError, OSError) as e:
        print(f"FALLÓ: {e!r}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
