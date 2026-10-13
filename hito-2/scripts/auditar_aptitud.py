#!/usr/bin/env python3
"""Hito 2, fase B: auditoría acústica acotada, sin exportar audio ni texto.

Ejecutar desde la raíz: .venv/bin/python -I hito-2/scripts/auditar_aptitud.py
Los registros del muestreo no constituyen evaluación de modelos ni censo acústico.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
from collections import Counter
from pathlib import Path

import pandas as pd

HITO = Path(__file__).resolve().parents[1]
SEMILLA = 20261010
MUESTRAS = {"common_voice": 10, "cordeba": 8, "callhome": 3}
TABLAS = {
    "asr_instancias": "asr_instancias.parquet",
    "asr_hablantes": "asr_hablantes.csv",
    "diarizacion_grabaciones": "diarizacion_grabaciones.csv",
    "diarizacion_segmentos": "diarizacion_segmentos.parquet",
    "diarizacion_hablantes": "diarizacion_hablantes.csv",
}
CAMPOS = (
    "fuente", "recording_id", "particion_original", "tipo_audio",
    "estado", "motivo", "duracion_observada_s", "duracion_referencia_s",
    "diferencia_duracion_s", "frecuencia_hz", "canales",
    "fin_ultima_anotacion_s", "exceso_anotacion_s",
)


def seleccionar(ids: list[str], n: int, sal: str) -> list[str]:
    """Orden aleatorio reproducible, independiente del orden del archivo."""
    if len(ids) != len(set(ids)):
        raise ValueError(f"Identificadores repetidos en {sal}")

    def clave(ident: str) -> str:
        return hashlib.sha256(f"{SEMILLA}:{sal}:{ident}".encode()).hexdigest()

    return sorted(ids, key=lambda ident: (clave(ident), ident))[:n]


def _numero(valor):
    if pd.isna(valor):
        return None
    try:
        f = float(valor)
    except (ValueError, TypeError):
        return None
    return f if math.isfinite(f) else None


def revisar_audio(ruta: Path, *, timeout: int = 120) -> dict:
    """Sondea formato y obliga a decodificar hasta EOF, no sólo leer cabecera."""
    try:
        meta = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=sample_rate,channels:format=duration",
             "-of", "json", str(ruta)],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        if meta.returncode != 0:
            return {"estado": "no_decodificable", "motivo": "ffprobe_fallo"}

        detalle = json.loads(meta.stdout)
        pistas = detalle.get("streams", [])
        if len(pistas) != 1:
            return {"estado": "no_decodificable", "motivo": "sin_pista_audio"}

        pista = pistas[0]
        hz = int(pista["sample_rate"])
        canales = int(pista["channels"])
        duracion = float(detalle.get("format", {}).get("duration", "nan"))

        if hz <= 0 or canales <= 0 or not math.isfinite(duracion) or duracion <= 0:
            return {"estado": "no_decodificable", "motivo": "metadatos_invalidos"}

        decodificar = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-xerror",
             "-i", str(ruta), "-map", "0:a:0", "-f", "null", "-"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout,
            check=False,
        )
        if decodificar.returncode != 0:
            return {"estado": "no_decodificable", "motivo": "ffmpeg_fallo"}

        return {
            "estado": "decodificable",
            "motivo": "",
            "duracion_observada_s": duracion,
            "frecuencia_hz": hz,
            "canales": canales,
        }
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return {"estado": "no_decodificable", "motivo": "formato_o_herramienta"}
    except subprocess.TimeoutExpired:
        return {"estado": "no_verificado", "motivo": "tiempo_agotado"}


def construir_fila(
    fuente: str,
    ident: str,
    tipo: str,
    ruta: Path | None,
    *,
    particion: str | None = None,
    esperado=None,
    ultimo=None,
) -> dict:
    fila = dict.fromkeys(CAMPOS, None)
    fila.update(
        fuente=fuente,
        recording_id=ident,
        particion_original=particion,
        tipo_audio=tipo,
        estado="ausente",
        motivo="archivo_no_disponible",
        duracion_referencia_s=_numero(esperado),
        fin_ultima_anotacion_s=_numero(ultimo),
    )

    if ruta is not None and ruta.is_file():
        fila.update(revisar_audio(ruta))

    if fila["estado"] == "decodificable":
        duracion = fila["duracion_observada_s"]
        if fila["duracion_referencia_s"] is not None:
            fila["diferencia_duracion_s"] = duracion - fila["duracion_referencia_s"]
        if fila["fin_ultima_anotacion_s"] is not None:
            fila["exceso_anotacion_s"] = max(
                0.0, fila["fin_ultima_anotacion_s"] - duracion
            )

    return fila


def _archivo_temporal(datos: bytes, carpeta: Path, nombre: str) -> Path:
    if not isinstance(datos, bytes) or not datos:
        raise ValueError("Bytes de audio ausentes")
    ruta = carpeta / nombre
    ruta.write_bytes(datos)
    return ruta


def _csv_lectura(ruta: Path) -> pd.DataFrame:
    return pd.read_csv(ruta, keep_default_na=False)


def _verificar_normalizado(base: Path) -> tuple[dict, dict[str, pd.DataFrame]]:
    manifest = json.loads(
        (base / "MANIFIESTO_NORMALIZADO.json").read_text(encoding="utf-8")
    )
    if manifest.get("estado") != "validado_estructuralmente_no_evaluado":
        raise ValueError("Se requiere una normalización estructuralmente validada")
    if set(manifest["tablas"]) != set(TABLAS):
        raise ValueError("Se esperan exactamente cinco tablas")

    tablas = {}
    for nombre, archivo in TABLAS.items():
        ruta = base / archivo
        contenido_sha = hashlib.sha256(ruta.read_bytes()).hexdigest()
        if contenido_sha != manifest["tablas"][nombre]["sha256"]:
            raise ValueError(f"SHA-256 diferente al manifiesto: {nombre}")

        df = (
            pd.read_parquet(ruta)
            if ruta.suffix == ".parquet"
            else _csv_lectura(ruta)
        )
        if len(df) != manifest["tablas"][nombre]["filas"]:
            raise ValueError(f"Conteo inconsistente: {nombre}")
        tablas[nombre] = df

    return manifest, tablas


def auditar(hito: Path = HITO, salida: Path | None = None) -> dict:
    """No modifica originales ni tablas; publica informe y CSV sin contenido sensible."""
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise RuntimeError("Se requieren ffprobe y ffmpeg para auditar audio")

    muestra, cache = hito / "muestra", hito / ".cache"
    destino = (
        salida if salida is not None
        else muestra / "normalizado" / "aptitud"
    )
    manifest, tablas = _verificar_normalizado(muestra / "normalizado")

    asr = tablas["asr_instancias"]
    dia = tablas["diarizacion_grabaciones"]
    segmentos = tablas["diarizacion_segmentos"]
    ultimo = segmentos.groupby(["source", "recording_id"])["end_s"].max().to_dict()
    filas = []

    # Common Voice: muestreo separado por partición.
    cv = asr[asr.source == "common_voice"]
    elegidos = {}
    for particion, grupo in cv.groupby("source_split"):
        for ident in seleccionar(
            grupo.recording_id.tolist(),
            MUESTRAS["common_voice"],
            f"common_voice:{particion}",
        ):
            elegidos[ident] = str(particion)

    config = tomllib.loads(
        (hito / "fuentes.toml").read_text(encoding="utf-8")
    )
    cv_tar = cache / "common_voice" / config["common_voice"]["archivo"]
    encontrados = set()

    with tempfile.TemporaryDirectory(prefix="aptitud-cv-") as td:
        carpeta = Path(td)
        with tarfile.open(cv_tar, "r|gz") as archivo:
            for entrada in archivo:
                if not entrada.isfile() or not entrada.name.endswith(".mp3"):
                    continue
                ident = Path(entrada.name).name
                if ident not in elegidos:
                    continue
                if (
                    ident in encontrados
                    or not entrada.name.endswith(f"/clips/{ident}")
                ):
                    raise ValueError(
                        f"Ruta MP3 inesperada o duplicada: {ident}"
                    )

                stream = archivo.extractfile(entrada)
                if stream is None:
                    raise ValueError(
                        f"MP3 seleccionado ilegible: {ident}"
                    )

                ruta = _archivo_temporal(stream.read(), carpeta, ident)
                filas.append(
                    construir_fila(
                        "common_voice", ident, "original",
                        ruta, particion=elegidos[ident],
                    )
                )
                ruta.unlink()
                encontrados.add(ident)

        for ident in elegidos.keys() - encontrados:
            filas.append(
                construir_fila(
                    "common_voice", ident, "original", None,
                    particion=elegidos[ident],
                )
            )

    # OpenSLR: clips derivados seleccionados previamente.
    slr = asr[asr.source == "slr61"]
    plan_slr = _csv_lectura(
        muestra / "slr61" / "transcripciones.csv"
    )
    plan = plan_slr.loc[
        plan_slr["en_muestra_de_audio"].astype(str).str.lower() == "true",
        "archivo",
    ].tolist()
    indices = slr.set_index("recording_id")

    for ident in plan:
        if ident not in indices.index:
            raise ValueError(
                "FLAC planificado sin registro en OpenSLR"
            )
        filas.append(
            construir_fila(
                "slr61", ident, "clip_recodificado",
                muestra / "slr61" / "clips" / f"{ident}.flac",
                esperado=indices.loc[ident, "duration_s"],
            )
        )

    # CORdeBA: muestra de originales más audios indexados como ilegibles.
    cord = asr[asr.source == "cordeba"]
    elegidos_cord = set(
        seleccionar(
            cord.recording_id.tolist(),
            MUESTRAS["cordeba"],
            "cordeba",
        )
    )
    elegidos_cord |= set(
        cord.loc[cord.audio_status != "valido", "recording_id"]
    )

    for fila in cord.itertuples(index=False):
        if fila.recording_id in elegidos_cord:
            filas.append(
                construir_fila(
                    "cordeba", fila.recording_id, "original",
                    cache / "cordeba" / fila.recording_id,
                    esperado=fila.duration_s,
                )
            )

    # Figshare: mezclas de inspección, no pistas originales completas.
    extractos = _csv_lectura(
        muestra / "uba_games_figshare" / "extractos.csv"
    )
    for fila in extractos.itertuples(index=False):
        ruta = muestra / "uba_games_figshare" / fila.archivo
        filas.append(
            construir_fila(
                "uba_games_figshare",
                fila.recording_id,
                "mezcla_derivada_30s",
                ruta,
                esperado=fila.duracion_s,
            )
        )

    # CALLHOME: muestra por archivo Parquet y fila, sin inferir sesiones.
    import pyarrow.parquet as pq

    ch = dia[dia.source == "callhome"]
    ids = set(ch.recording_id)
    shards = sorted(
        (cache / "callhome").glob("data-*.parquet")
    )
    if not shards:
        raise ValueError("No hay originales CALLHOME")

    for ruta in shards:
        parquet = pq.ParquetFile(ruta)
        claves = [
            f"{ruta.stem}:row{i:04d}"
            for i in range(parquet.metadata.num_rows)
        ]
        seleccion = set(
            seleccionar(
                claves, MUESTRAS["callhome"], ruta.name
            )
        )

        with tempfile.TemporaryDirectory(
            prefix="aptitud-callhome-"
        ) as td:
            carpeta = Path(td)
            vistos = set()

            for i, batch in enumerate(
                parquet.iter_batches(
                    batch_size=1, columns=["audio"]
                )
            ):
                ident = f"{ruta.stem}:row{i:04d}"
                if ident not in seleccion:
                    continue
                if ident not in ids:
                    raise ValueError(
                        f"CALLHOME: registro no normalizado: {ident}"
                    )

                audio = batch.to_pylist()[0]["audio"]
                datos = (
                    audio.get("bytes")
                    if isinstance(audio, dict) else None
                )
                ruta_audio = (
                    _archivo_temporal(
                        datos, carpeta, f"row{i:04d}.bin"
                    )
                    if isinstance(datos, bytes) and datos
                    else None
                )

                filas.append(
                    construir_fila(
                        "callhome",
                        ident,
                        "original_embebido",
                        ruta_audio,
                        ultimo=ultimo.get(("callhome", ident)),
                    )
                )
                if ruta_audio is not None:
                    ruta_audio.unlink()

                vistos.add(ident)
                if vistos == seleccion:
                    break

            if vistos != seleccion:
                raise ValueError(
                    f"CALLHOME: filas no encontradas en {ruta.name}"
                )

    # Generación del resumen.
    filas.sort(
        key=lambda x: (
            x["fuente"],
            x["particion_original"] or "",
            x["recording_id"],
        )
    )
    resumen = {}
    universo = {
        "common_voice": len(cv),
        "slr61": len(slr),
        "cordeba": len(cord),
        "uba_games_figshare": int(
            (dia.source == "uba_games_figshare").sum()
        ),
        "callhome": len(ch),
    }

    for fuente, total in universo.items():
        grupo = [
            r for r in filas if r["fuente"] == fuente
        ]
        estados = Counter(
            r["estado"] for r in grupo
        )
        diferencias = [
            abs(r["diferencia_duracion_s"])
            for r in grupo
            if r["diferencia_duracion_s"] is not None
        ]
        excesos = [
            r["exceso_anotacion_s"]
            for r in grupo
            if r["exceso_anotacion_s"] is not None
        ]

        resumen[fuente] = {
            "registros_normalizados": total,
            "audios_inspeccionados": len(grupo),
            "decodificables": estados["decodificable"],
            "no_decodificables": estados["no_decodificable"],
            "ausentes": estados["ausente"],
            "sin_verificar": estados["no_verificado"],
            "max_diferencia_absoluta_duracion_s": max(
                diferencias, default=None
            ),
            "max_exceso_anotacion_s": max(
                excesos, default=None
            ),
            "tipo_evidencia": sorted({
                r["tipo_audio"] for r in grupo
            }),
        }

    reporte = {
        "version": 1,
        "semilla": SEMILLA,
        "muestreo_por_particion_cv": MUESTRAS["common_voice"],
        "muestreo_cordeba": MUESTRAS["cordeba"],
        "muestreo_callhome_por_parquet": MUESTRAS["callhome"],
        "tablas_origen_sha256": {
            k: v["sha256"]
            for k, v in manifest["tablas"].items()
        },
        "resumen": resumen,
        "advertencias": [
            "Muestreo acústico: las proporciones observadas no son mediciones del corpus completo.",
            "OpenSLR se inspecciona sobre hasta 44 FLAC derivados; Figshare sobre las mezclas de inspección disponibles.",
            "Los WAV individuales Figshare y los clips completos OpenSLR tienen verificaciones previas en fase A.",
            "Decodificar audio no comprueba exactitud de texto, identidad ni alineación de anotaciones.",
            "No se genera RTTM, transcripción corregida, particiones ni audio redistribuible.",
            "Los 140 registros CALLHOME no acreditan 140 sesiones independientes.",
        ],
    }

    # Publicación de resultados sin sobrescribir parcialmente.
    destino.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="aptitud-build-",
        dir=destino.parent,
    ) as td:
        tmp = Path(td)

        with (tmp / "RESULTADOS_B.csv").open(
            "w", encoding="utf-8", newline=""
        ) as f:
            escritor = csv.DictWriter(
                f, fieldnames=CAMPOS
            )
            escritor.writeheader()
            escritor.writerows(filas)

        (tmp / "INFORME_B.json").write_text(
            json.dumps(
                reporte,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )

        with (tmp / "RESULTADOS_B.csv").open(
            encoding="utf-8", newline=""
        ) as f:
            if sum(1 for _ in csv.DictReader(f)) != len(filas):
                raise ValueError(
                    "La salida CSV no conserva todas las filas"
                )

        anterior = tmp / "anterior"
        if destino.exists():
            destino.rename(anterior)

        try:
            destino.mkdir()
            for archivo in (
                "RESULTADOS_B.csv",
                "INFORME_B.json",
            ):
                (tmp / archivo).replace(destino / archivo)
        except BaseException:
            if destino.exists():
                shutil.rmtree(destino)
            if anterior.exists():
                anterior.rename(destino)
            raise

    return reporte


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.parse_args()

    resumen = auditar()
    print(
        json.dumps(
            resumen["resumen"],
            ensure_ascii=False,
            indent=2,
        )
    )
    print(
        "Informe: hito-2/muestra/normalizado/aptitud/INFORME_B.json"
    )
    print(
        "Detalle: hito-2/muestra/normalizado/aptitud/RESULTADOS_B.csv"
    )


if __name__ == "__main__":
    main()