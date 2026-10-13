#!/usr/bin/env python3
"""Adquiere fuentes crudas verificadas en hito-2/.cache/.

Uso: python3 -I hito-2/scripts/descargar_fuentes.py [grupo ...]

Grupos: principales (por defecto), anotaciones, audio, castellano,
        slr61, cordeba, humyn, callhome, common_voice, uba_games, comprobar.

La primera adquisición fija hashes locales y revisiones de Hugging Face
en fuentes.lock.json. Versionar ese archivo después de verificar el
inventario adquirido.

El audio completo de AMI e ICSI no se descarga: se construyen índices
y extractos de 30 segundos.
"""
from __future__ import annotations

import csv
import json
import os
import random
import re
import struct
import sys
import tarfile
import tomllib
import urllib.error
import urllib.request
import wave
import zipfile
from pathlib import Path

# El modo -I excluye el directorio del script de sys.path.
# Incorporar explícitamente la ubicación del módulo auxiliar.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from adquisicion import (
    bajar as descarga_http, cargar_json, guardar_json,
    incorporar_local, pedir_rango, registro, sha256, validar,
)

SEMILLA = 20261010
HITO = Path(__file__).resolve().parent.parent
CACHE = HITO / ".cache"
LOCK_PATH = HITO / "fuentes.lock.json"
REGISTRO = tomllib.loads(
    (HITO / "fuentes.toml").read_text(encoding="utf-8")
)
HISTORICO = cargar_json(
    HITO / "muestra" / "MANIFIESTO.json"
).get("archivos_crudos", {})
LOCK = cargar_json(
    LOCK_PATH,
    {"version": 1, "archivos": {}, "repos": {}},
)
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

SLR61 = {
    f"slr61/{nombre}": f"https://www.openslr.org/resources/61/{nombre}"
    for nombre in (
        "line_index_female.tsv",
        "line_index_male.tsv",
        "es_ar_male.zip",
        "es_ar_female.zip",
    )
}

# Cuántos extractos por grupo de reuniones (prefijo del identificador).
EXTRACTOS = {"ami": {"ES": 4, "IS": 4, "TS": 4, "EN": 2, "IB": 2}, "icsi": {"Bmr": 3, "Bro": 3, "Bed": 2}}
SEGUNDOS = 30


def fijar_archivo(destino: Path, datos: dict) -> None:
    clave = destino.relative_to(CACHE).as_posix()
    anterior = LOCK["archivos"].get(clave)

    if anterior and anterior != datos:
        raise ValueError(f"Cambió un archivo fijado: {clave}")

    LOCK["archivos"][clave] = datos
    guardar_json(LOCK_PATH, LOCK)


def esperado(destino: Path) -> dict | None:
    clave = destino.relative_to(CACHE).as_posix()
    anterior = LOCK["archivos"].get(clave)
    historico = HISTORICO.get(clave)

    if historico and anterior and historico != anterior:
        raise ValueError(
            f"Conflicto entre referencia histórica y lock: {clave}"
        )

    return anterior or historico


def bajar(url: str, destino: Path) -> None:
    datos = descarga_http(url, destino, esperado(destino))
    fijar_archivo(destino, datos)
    print(
        f"  ok {destino.relative_to(CACHE)} "
        f"({datos['bytes']} bytes)"
    )


def importar(origen: Path, destino: Path) -> None:
    datos = incorporar_local(origen, destino, esperado(destino))
    fijar_archivo(destino, datos)
    print(
        f"  ok {destino.relative_to(CACHE)} "
        f"({datos['bytes']} bytes)"
    )


def repositorio_hf(nombre: str) -> None:
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError as e:
        raise RuntimeError(
            "Instalá huggingface_hub según requirements-adquisicion.txt"
        ) from e

    cfg = REGISTRO["huggingface"][nombre]
    token = os.environ.get("HF_TOKEN")

    if cfg.get("autenticado") and not token:
        raise RuntimeError(
            "Falta HF_TOKEN y acceso individual aprobado"
        )

    api = HfApi(token=token)
    previo = LOCK["repos"].get(nombre)

    sha = (
        previo["revision"]
        if previo
        else api.repo_info(
            repo_id=cfg["repo"],
            repo_type="dataset",
        ).sha
    )

    archivos = sorted(
        api.list_repo_files(
            repo_id=cfg["repo"],
            repo_type="dataset",
            revision=sha,
        )
    )

    if nombre == "cordeba":
        elegidos = [
            f for f in archivos
            if f == "metadata.csv"
            or (
                f.startswith(cfg["prefijo"])
                and f.lower().endswith((".mp3", ".wma", ".wav"))
            )
        ]
        if "metadata.csv" not in elegidos or len(elegidos) < 2:
            raise ValueError("Inventario CORdeBA incompleto")
    else:
        elegidos = [
            f for f in archivos
            if f.startswith(cfg["prefijo"])
            and f.endswith(".parquet")
        ]
        if not elegidos:
            raise ValueError(f"Inventario vacío: {nombre}")

    if len({Path(x).name for x in elegidos}) != len(elegidos):
        raise ValueError(
            f"Archivos con nombres locales duplicados: {nombre}"
        )

    if previo and previo["archivos"] != elegidos:
        raise ValueError(
            f"Inventario remoto cambió para la revisión fijada: {nombre}"
        )

    LOCK["repos"][nombre] = {
        "repo": cfg["repo"],
        "revision": sha,
        "archivos": elegidos,
    }
    guardar_json(LOCK_PATH, LOCK)

    for archivo in elegidos:
        destino = CACHE / nombre / Path(archivo).name

        if destino.exists():
            datos = esperado(destino)
            if not validar(destino, datos):
                raise ValueError(
                    f"Archivo preexistente no verificable: {destino}"
                )
            print(f"  ok (verificado) {destino.name}")
            continue

        origen = hf_hub_download(
            repo_id=cfg["repo"],
            filename=archivo,
            revision=sha,
            repo_type="dataset",
            token=token,
            cache_dir=str(CACHE / "_hf"),
        )
        importar(Path(origen), destino)

    if nombre == "cordeba":
        with (
            CACHE / "cordeba" / "metadata.csv"
        ).open(newline="", encoding="utf-8") as f:
            lector = csv.DictReader(f)
            if "file_name" not in (lector.fieldnames or []):
                raise ValueError(
                    "CORdeBA: falta columna file_name"
                )
            referencias = [
                Path(r["file_name"]).name for r in lector
            ]

        audios = [
            Path(x).name
            for x in elegidos
            if x != "metadata.csv"
        ]

        if (
            len(referencias) != len(set(referencias))
            or set(referencias) != set(audios)
        ):
            raise ValueError(
                "CORdeBA: metadata.csv no coincide "
                "con inventario de audio"
            )


def common_voice() -> None:
    if not os.environ.get("MDC_API_KEY"):
        raise RuntimeError(
            "Falta MDC_API_KEY y acceso autorizado"
        )

    try:
        from datacollective import download_dataset
    except ImportError as e:
        raise RuntimeError(
            "Instalá datacollective según "
            "requirements-adquisicion.txt"
        ) from e

    cfg = REGISTRO["common_voice"]
    destino = CACHE / "common_voice" / cfg["archivo"]
    datos = esperado(destino)

    if destino.exists():
        if not validar(destino, datos):
            raise ValueError(
                "Archivo Common Voice preexistente no verificable"
            )
        return

    origen = Path(
        download_dataset(
            cfg["id"],
            download_directory=str(CACHE / "_mdc"),
        )
    )

    if origen.name != cfg["archivo"]:
        raise ValueError(
            f"MDC publicó otro archivo: {origen.name}"
        )

    with tarfile.open(origen, "r:gz") as z:
        if not z.getmembers():
            raise ValueError("Archivo MDC vacío")

    importar(origen, destino)


def uba_games() -> None:
    cfg = REGISTRO["uba_games"]
    enlaces = cfg.get("urls", {})
    archivos = cfg["archivos"]

    if set(enlaces) != set(archivos) or not all(
        isinstance(url, str) and url.startswith("https://")
        for url in enlaces.values()
    ):
        raise RuntimeError(
            "UBA Games: faltan URLs individuales verificadas. "
            "No se descargan archivos mediante enlaces ambiguos."
        )

    for archivo in archivos:
        bajar(
            enlaces[archivo],
            CACHE / "uba_games" / archivo,
        )


def uba_games_figshare() -> None:
    """Adquiere los dos RAR oficiales como una distribución separada."""
    cfg = REGISTRO["uba_games_figshare"]
    for nombre, info in sorted(cfg["archivos"].items()):
        destino = CACHE / "uba_games" / "figshare-v2" / nombre
        datos = descarga_http(
            f"https://ndownloader.figshare.com/files/{info['file_id']}",
            destino,
            esperado(destino),
            md5_esperado=info["md5"],
            bytes_esperados=info["bytes"],
        )
        fijar_archivo(destino, datos)
        print(f"  ok {destino.relative_to(CACHE)} ({datos['bytes']} bytes)")


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
        registro(destino, CACHE, LOCK)
        return json.loads(destino.read_text(encoding="utf-8"))
    indice = {"ami": {}, "icsi": {}, "voxconverse": {}}
    for corpus, patron in (("ami", AUDIO_AMI), ("icsi", AUDIO_ICSI)):
        ids = reuniones()[corpus]
        for i, r in enumerate(ids, 1):
            url, fila = patron.format(r=r), {}
            try:
                cabecera, total = pedir_rango(url, 0, 4095)
                cab = leer_cabecera_wav(cabecera)
                fila = {"url": url, "disponible": True, "bytes": total, **cab,
                        "duracion_s": (total - cab["inicio_datos"]) / cab["bytes_por_cuadro"] / cab["hz"]}
            except (urllib.error.URLError, ValueError, KeyError, struct.error) as e:
                fila = {"url": url, "disponible": False, "error": repr(e)[:160]}
            indice[corpus][r] = fila
            if i % 25 == 0 or i == len(ids):
                print(f"  {corpus}: {i}/{len(ids)}")
    for corpus in ("ami", "icsi"):
        if not any(
            f.get("disponible")
            for f in indice[corpus].values()
        ):
            raise ValueError(
                f"Sin audio verificable para {corpus}; "
                "no guardar índice"
            )

    for particion, url in AUDIO_VOX.items():
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=120) as resp:
                indice["voxconverse"][particion] = {
                    "url": url,
                    "disponible": True,
                    "bytes": int(resp.headers["Content-Length"]),
                }
        except urllib.error.URLError as e:
            indice["voxconverse"][particion] = {"url": url, "disponible": False, "error": repr(e)[:160]}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(indice, indent=1),
        encoding="utf-8",
    )
    fijar_archivo(
        destino,
        {
            "bytes": destino.stat().st_size,
            "sha256": sha256(destino),
        },
    )
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
        if destino.exists():
            registro(destino, CACHE, LOCK)
        else:
            desde = (
                f["inicio_datos"]
                + p["inicio_s"] * f["hz"] * f["bytes_por_cuadro"]
            )
            hasta = (
                desde
                + SEGUNDOS * f["hz"] * f["bytes_por_cuadro"]
                - 1
            )

            crudo, total = pedir_rango(
                f["url"], desde, hasta
            )

            if total != f["bytes"]:
                raise ValueError(
                    f"Cambió el archivo remoto: {p['reunion']}"
                )

            temporal = destino.with_suffix(".wav.part")

            with wave.open(str(temporal), "wb") as w:
                w.setnchannels(f["canales"])
                w.setsampwidth(f["bits"] // 8)
                w.setframerate(f["hz"])
                w.writeframes(crudo)

            os.replace(temporal, destino)
            fijar_archivo(
                destino,
                {
                    "bytes": destino.stat().st_size,
                    "sha256": sha256(destino),
                },
            )

        print(
            f"  ok  {destino.name} "
            f"desde el segundo {p['inicio_s']}"
        )

    plan_destino = carpeta / "plan.json"

    if plan_destino.exists():
        registro(plan_destino, CACHE, LOCK)
        if json.loads(plan_destino.read_text()) != plan:
            raise ValueError(
                "El plan anterior difiere del plan calculado"
            )
    else:
        plan_destino.write_text(
            json.dumps(plan, indent=1),
            encoding="utf-8",
        )
        fijar_archivo(
            plan_destino,
            {
                "bytes": plan_destino.stat().st_size,
                "sha256": sha256(plan_destino),
            },
        )


def audio() -> None:
    print("[audio]")
    extractos(indice_de_audio())


def slr61() -> None:
    print("[slr61]")
    for destino, url in SLR61.items():
        bajar(url, CACHE / destino)


def castellano() -> None:
    slr61()
    repositorio_hf("cordeba")
    repositorio_hf("humyn")


def comprobar() -> None:
    if not LOCK["archivos"]:
        raise ValueError(
            "No hay adquisiciones fijadas en fuentes.lock.json"
        )

    for nombre, info in LOCK["repos"].items():
        faltantes = [
            f"{nombre}/{Path(archivo).name}"
            for archivo in info["archivos"]
            if f"{nombre}/{Path(archivo).name}"
            not in LOCK["archivos"]
        ]

        if faltantes:
            raise ValueError(
                f"Repositorio {nombre} adquirido parcialmente: "
                f"{faltantes}"
            )

    prefijo = "uba_games/figshare-v2/"
    if any(x.startswith(prefijo) for x in LOCK["archivos"]):
        esperados = {prefijo + n for n in REGISTRO["uba_games_figshare"]["archivos"]}
        presentes = {x for x in LOCK["archivos"] if x.startswith(prefijo)}
        if esperados != presentes:
            raise ValueError("Figshare v2: inventario registrado incompleto")
    for ruta in sorted(LOCK["archivos"]):
        registro(CACHE / ruta, CACHE, LOCK)

    print(
        f"Integridad de {len(LOCK['archivos'])} archivos confirmada; "
        "no acredita completitud del corpus de origen"
    )


def main(argv: list[str]) -> int:
    pasos = {
        "anotaciones": anotaciones,
        "audio": audio,
        "castellano": castellano,
        "slr61": slr61,
        "cordeba": lambda: repositorio_hf("cordeba"),
        "humyn": lambda: repositorio_hf("humyn"),
        "callhome": lambda: repositorio_hf("callhome"),
        "common_voice": common_voice,
        "uba_games": uba_games,
        "uba_games_figshare": uba_games_figshare,
        "comprobar": comprobar,
    }

    # UBA Games permanece bloqueado hasta verificar sus URLs.
    grupos = {
        "principales": [
            "anotaciones",
            "slr61",
            "cordeba",
            "common_voice",
            "uba_games_figshare",
        ]
    }

    nombres = [
        x
        for n in (argv or ["principales"])
        for x in grupos.get(n, [n])
    ]

    desconocidos = sorted(set(nombres) - set(pasos))
    if desconocidos:
        print(
            f"Argumentos desconocidos: "
            f"{', '.join(desconocidos)}"
        )
        return 2

    try:
        for nombre in nombres:
            print(f"[{nombre}]")
            pasos[nombre]()
    except (
        urllib.error.URLError,
        KeyError,
        OSError,
        ValueError,
        RuntimeError,
        zipfile.BadZipFile,
    ) as e:
        print(f"FALLÓ: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
