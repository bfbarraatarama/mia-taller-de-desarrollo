"""Materializa el contrato compartido para ASR y diarización.

Los datos normalizados son derivados de trabajo, no corpus redistribuibles.
El pipeline conserva los archivos específicos y no decide su viabilidad.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import tarfile
import tempfile
import tomllib
from collections import Counter
from pathlib import Path

import pandas as pd

from validar_muestra import ARCHIVOS, COLUMNAS, validar_tablas

SCHEMA_VERSION = 1
FUENTES = (
    "common_voice",
    "slr61",
    "cordeba",
    "uba_games_figshare",
    "callhome",
)


def _tabla(nombre: str, filas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(filas, columns=COLUMNAS[nombre])


def _text(v) -> str | None:
    if v is None or bool(pd.isna(v)):
        return None
    s = str(v).strip()
    return s or None


def _sumar(destino: dict[str, list[dict]], fuente: dict[str, list[dict]]) -> None:
    for tabla, filas in fuente.items():
        destino[tabla].extend(filas)


def _filas_asr() -> dict[str, list[dict]]:
    return {"asr_instancias": [], "asr_hablantes": []}


def _filas_dia() -> dict[str, list[dict]]:
    return {
        "diarizacion_grabaciones": [],
        "diarizacion_segmentos": [],
        "diarizacion_hablantes": [],
    }


def common_voice(tar_path: Path) -> tuple[dict[str, list[dict]], dict]:
    """Usa todos los TSV y comprueba correspondencia biunívoca con los MP3."""
    tablas = _filas_asr()
    mp3: set[str] = set()
    muestras: list[tuple[str, str, dict]] = []
    vistos: set[str] = set()
    for_split = Counter()

    with tarfile.open(tar_path, "r|gz") as tar:
        for item in tar:
            if not item.isfile():
                continue

            path = item.name
            if path.startswith("/") or ".." in Path(path).parts:
                raise ValueError(f"Ruta no segura en Common Voice: {path}")

            if path.endswith(".mp3"):
                if path in mp3:
                    raise ValueError(f"MP3 duplicado en TAR: {path}")
                mp3.add(path)

            elif path.endswith(".tsv"):
                split = Path(path).name.removesuffix(".tsv")
                if split not in {"train", "dev", "test"}:
                    raise ValueError(f"TSV desconocido de Common Voice: {path}")

                fileobj = tar.extractfile(item)
                if fileobj is None:
                    raise ValueError(f"TSV ilegible: {path}")

                lector = csv.DictReader(
                    (line.decode("utf-8-sig") for line in fileobj),
                    delimiter="\t",
                )
                if not {"path", "sentence", "client_id"}.issubset(
                    lector.fieldnames or []
                ):
                    raise ValueError(f"TSV sin columnas requeridas: {path}")

                for numero, row in enumerate(lector, 2):
                    archivo = _text(row["path"])
                    if not archivo or Path(archivo).name != archivo:
                        raise ValueError(
                            f"Nombre de MP3 inválido en {path}:{numero}"
                        )
                    if archivo in vistos:
                        raise ValueError(
                            f"Clip repetido entre particiones: {archivo}"
                        )
                    vistos.add(archivo)
                    muestras.append((split, path, row))
                    for_split[split] += 1

    encontrados = {Path(p).name for p in mp3}
    if len(encontrados) != len(mp3) or vistos != encontrados:
        raise ValueError(
            f"Common Voice: TSV/MP3 no biyectivos; "
            f"faltan {len(vistos - encontrados)}, "
            f"sobran {len(encontrados - vistos)}"
        )

    speakers: dict[str, dict] = {}
    for split, tsv, row in muestras:
        filename = _text(row["path"])
        client = _text(row["client_id"])
        sid = f"cv:{client}" if client else None

        if sid and sid not in speakers:
            speakers[sid] = dict(
                source="common_voice",
                speaker_id=sid,
                source_speaker_id=client,
                speaker_scope="source",
                session_id=None,
                recording_id=None,
            )

        tablas["asr_instancias"].append(dict(
            source="common_voice",
            recording_id=filename,
            source_recording_id=filename,
            session_id=None,
            group_id=sid,
            speaker_id=sid,
            duration_s=None,
            audio_ref=f"common_voice:TAR#{filename}",
            audio_status="no_verificado",
            reference_raw=_text(row["sentence"]),
            reference_norm=None,
            reference_origin=tsv,
            reference_scope="recording",
            language=_text(row.get("locale")) or "es-Rioplatense",
            source_split=split,
            project_split=None,
        ))

    tablas["asr_hablantes"].extend(speakers.values())
    return tablas, {
        "clips": len(muestras),
        "mp3": len(mp3),
        "particiones": dict(for_split),
    }


def slr61(muestra: Path) -> tuple[dict[str, list[dict]], dict]:
    tablas = _filas_asr()
    trans = pd.read_csv(
        muestra / "slr61/transcripciones.csv",
        keep_default_na=False,
    )
    audio = pd.read_csv(
        muestra / "slr61/manifiesto_audio.csv",
        keep_default_na=False,
    )

    if trans["archivo"].duplicated().any() or audio["archivo"].duplicated().any():
        raise ValueError("OpenSLR: IDs repetidos")

    formatos = {str(f["archivo"]): f for _, f in audio.iterrows()}
    speakers: set[str] = set()

    for _, f in trans.iterrows():
        name = str(f["archivo"])
        a = formatos.get(name)
        sp = _text(f["hablante"])
        sid = f"slr61:{sp}" if sp else None

        dur = (
            float(a["duracion_s"])
            if a is not None
            and pd.notna(a["duracion_s"])
            and a["duracion_s"] != ""
            else None
        )
        legible = a is not None and str(a["legible"]).lower() == "true"

        if sid and sid not in speakers:
            speakers.add(sid)
            tablas["asr_hablantes"].append(dict(
                source="slr61",
                speaker_id=sid,
                source_speaker_id=sp,
                speaker_scope="source",
                session_id=None,
                recording_id=None,
            ))

        tablas["asr_instancias"].append(dict(
            source="slr61",
            recording_id=name,
            source_recording_id=name,
            session_id=None,
            group_id=sid,
            speaker_id=sid,
            duration_s=dur,
            audio_ref=f"slr61:{name}" if a is not None else None,
            audio_status=(
                "valido" if legible and dur and dur > 0
                else "ilegible" if a is not None
                else "no_disponible"
            ),
            reference_raw=_text(f["texto"]),
            reference_norm=None,
            reference_origin="slr61/transcripciones.csv",
            reference_scope="recording",
            language="es-AR",
            source_split=None,
            project_split=None,
        ))

    return tablas, {
        "instancias": len(trans),
        "con_audio_indexado": len(formatos),
    }


def cordeba(muestra: Path) -> tuple[dict[str, list[dict]], dict]:
    tablas = _filas_asr()
    grabaciones = pd.read_csv(
        muestra / "cordeba/grabaciones.csv",
        keep_default_na=False,
    )
    turnos = pd.read_parquet(muestra / "cordeba/turnos.parquet")

    if grabaciones["archivo"].duplicated().any():
        raise ValueError("CORdeBA: ID de archivo duplicado")

    conjunto = set(grabaciones["archivo"])
    if not set(turnos["archivo"]).issubset(conjunto):
        raise ValueError("CORdeBA: turnos sin grabación")

    por_archivo = {}
    for name, group in turnos.groupby("archivo", sort=False):
        group = group.sort_values("orden", kind="stable")
        por_archivo[name] = " ".join(
            str(t).strip() for t in group["texto"] if _text(t)
        )

    for _, f in grabaciones.iterrows():
        name = str(f["archivo"])
        legible = str(f["legible"]).lower() == "true"
        dur = (
            float(f["duracion_s"])
            if f["duracion_s"] != "" and pd.notna(f["duracion_s"])
            else None
        )

        tablas["asr_instancias"].append(dict(
            source="cordeba",
            recording_id=name,
            source_recording_id=name,
            session_id=None,
            group_id=None,
            speaker_id=None,
            duration_s=dur,
            audio_ref=f"cordeba:{name}",
            audio_status=(
                "valido" if legible and dur and dur > 0 else "ilegible"
            ),
            reference_raw=_text(por_archivo.get(name)),
            reference_norm=None,
            reference_origin="cordeba/turnos.parquet",
            reference_scope="recording",
            language="es-AR",
            source_split=None,
            project_split=None,
        ))

    return tablas, {
        "grabaciones": len(grabaciones),
        "referencias_no_vacias": sum(
            bool(x) for x in por_archivo.values()
        ),
    }


def figshare(muestra: Path) -> tuple[dict[str, list[dict]], dict]:
    tablas = _filas_dia()
    raiz = muestra / "uba_games_figshare"
    grab = pd.read_csv(
        raiz / "grabaciones.csv",
        keep_default_na=False,
    )
    seg = pd.read_parquet(raiz / "intervalos.parquet")
    sp = pd.read_csv(
        raiz / "hablantes.csv",
        keep_default_na=False,
    )

    for _, f in grab.iterrows():
        ident = str(f["recording_id"])
        dur = f["duracion_s"]
        dur = float(dur) if dur != "" and pd.notna(dur) else None

        tablas["diarizacion_grabaciones"].append(dict(
            source="uba_games_figshare",
            recording_id=ident,
            source_recording_id=ident,
            session_id=str(f["session_id"]),
            group_id=str(f["group_id"]),
            duration_s=dur,
            audio_ref=f"uba_games_figshare:phrases_wavs#{ident}",
            # Las pistas originales no equivalen a una mezcla completa.
            audio_status="no_verificado",
            reference_origin="figshare:v2:phrases.rar",
            source_split=None,
            project_split=None,
        ))

    for _, f in seg.iterrows():
        silencio = bool(f["silencio_marcado"])
        tablas["diarizacion_segmentos"].append(dict(
            source="uba_games_figshare",
            recording_id=str(f["recording_id"]),
            speaker_id=None if silencio else str(f["speaker_id"]),
            start_s=float(f["inicio_s"]),
            end_s=float(f["fin_s"]),
            annotation_raw=str(f["texto_original"]),
            is_silence_marker=silencio,
            scored_as_speech=False if silencio else None,
            reference_origin=str(f["origen_anotacion"]),
        ))

    # No extender identidades de canales a sesiones diferentes.
    for (session, sid), group in sp.groupby(
        ["session_id", "speaker_id"],
        sort=True,
    ):
        tablas["diarizacion_hablantes"].append(dict(
            source="uba_games_figshare",
            speaker_id=str(sid),
            source_speaker_id=f"channel{int(group.iloc[0]['canal'])}",
            speaker_scope="session",
            session_id=str(session),
            recording_id=None,
        ))

    return tablas, {
        "grabaciones": len(grab),
        "intervalos": len(seg),
        "sesiones": grab["session_id"].nunique(),
    }


def callhome(cache: Path) -> tuple[dict[str, list[dict]], dict]:
    """Conserva las etiquetas sin inferir identidades entre registros."""
    import pyarrow.parquet as pq

    tablas = _filas_dia()
    archivos = sorted((cache / "callhome").glob("data-*.parquet"))
    if not archivos:
        raise ValueError("CALLHOME no está adquirido")

    conteo = 0
    anomalías: list[dict] = []
    intervalos_totales = 0
    for archivo in archivos:
        parquet = pq.ParquetFile(archivo)
        necesarias = {
            "audio",
            "timestamps_start",
            "timestamps_end",
            "speakers",
        }
        if not necesarias.issubset(parquet.schema_arrow.names):
            raise ValueError(
                f"CALLHOME: columnas inesperadas en {archivo.name}"
            )

        posicion = 0
        for lote in parquet.iter_batches(batch_size=1):
            row = lote.to_pylist()[0]
            starts, ends, labels = (
                row[x]
                for x in (
                    "timestamps_start",
                    "timestamps_end",
                    "speakers",
                )
            )

            if (
                starts is None
                or ends is None
                or labels is None
                or not (len(starts) == len(ends) == len(labels))
            ):
                raise ValueError(
                    f"CALLHOME: listas desalineadas "
                    f"en {archivo.name}:{posicion}"
                )

            if row["audio"] is None or not row["audio"].get("bytes"):
                raise ValueError(
                    f"CALLHOME: no hay bytes de audio "
                    f"en {archivo.name}:{posicion}"
                )

            ident = f"{archivo.stem}:row{posicion:04d}"
            ref = f"callhome:{archivo.name}#row={posicion}"

            tablas["diarizacion_grabaciones"].append(dict(
                source="callhome",
                recording_id=ident,
                source_recording_id=ident,
                session_id=None,
                group_id=None,
                duration_s=None,
                audio_ref=ref,
                audio_status="no_verificado",
                reference_origin=ref,
                source_split=None,
                project_split=None,
            ))

            speakers = set()
            for indice, (start, end, speaker) in enumerate(
                zip(starts, ends, labels)
            ):
                intervalos_totales += 1
                if not (
                    isinstance(start, (int, float))
                    and not isinstance(start, bool)
                    and isinstance(end, (int, float))
                    and not isinstance(end, bool)
                    and math.isfinite(start)
                    and math.isfinite(end)
                ):
                    raise ValueError(
                        f"CALLHOME: tiempo ausente o no finito en "
                        f"{ident}, intervalo {indice}"
                    )

                if not 0 <= start < end:
                    anomalías.append({
                        "archivo": archivo.name,
                        "fila": posicion,
                        "indice_intervalo": indice,
                        "recording_id": ident,
                        "inicio_s": float(start),
                        "fin_s": float(end),
                        "etiqueta_hablante": speaker,
                        "motivo": "intervalo_temporal_invalido",
                    })
                    continue

                label = _text(speaker)
                sid = f"{ident}:{label}" if label is not None else None

                if sid is not None:
                    speakers.add((sid, label))

                tablas["diarizacion_segmentos"].append(dict(
                    source="callhome",
                    recording_id=ident,
                    speaker_id=sid,
                    start_s=float(start),
                    end_s=float(end),
                    annotation_raw=None,
                    is_silence_marker=None,
                    scored_as_speech=None,
                    reference_origin=ref,
                ))

            for sid, label in sorted(speakers):
                tablas["diarizacion_hablantes"].append(dict(
                    source="callhome",
                    speaker_id=sid,
                    source_speaker_id=label,
                    speaker_scope="recording",
                    session_id=None,
                    recording_id=ident,
                ))

            posicion += 1
            conteo += 1

    return tablas, {
        "registros": conteo,
        "intervalos_originales": intervalos_totales,
        "intervalos": len(tablas["diarizacion_segmentos"]),
        "intervalos_invalidos": len(anomalías),
        "grupos_de_sesion_identificados": 0,
        "_anomalias": anomalías,
    }


def materializar(
    muestra: Path,
    cache: Path,
    destino: Path,
    fuentes: tuple[str, ...] = FUENTES,
) -> dict:
    """Valida y publica la normalización sin dejar salidas parciales."""
    fuentes = tuple(dict.fromkeys(fuentes))
    desconocidas = set(fuentes) - set(FUENTES)

    if not fuentes or desconocidas:
        raise ValueError(
            f"Fuentes desconocidas o vacías: {desconocidas}"
        )

    resultados: dict[str, dict] = {}
    frames: dict[str, list[dict] | pd.DataFrame] = {
        x: [] for x in ARCHIVOS
    }
    resumen = {}
    anomalías_callhome: list[dict] | None = None

    config = tomllib.loads(
        (cache.parent / "fuentes.toml").read_text(encoding="utf-8")
    )

    adaptadores = {
        "common_voice": lambda: common_voice(
            cache / "common_voice" / config["common_voice"]["archivo"]
        ),
        "slr61": lambda: slr61(muestra),
        "cordeba": lambda: cordeba(muestra),
        "uba_games_figshare": lambda: figshare(muestra),
        "callhome": lambda: callhome(cache),
    }

    for fuente in fuentes:
        tablas, estado = adaptadores[fuente]()
        _sumar(frames, tablas)
        estado = dict(estado)
        if fuente == "callhome":
            anomalías_callhome = estado.pop("_anomalias")
            if (
                estado["intervalos_invalidos"] != len(anomalías_callhome)
                or estado["intervalos_originales"] != (
                    estado["intervalos"] + len(anomalías_callhome)
                )
            ):
                raise ValueError("CALLHOME: conteos de anomalías inconsistentes")
        resumen[fuente] = estado

    has_asr = any(
        x in fuentes for x in ("slr61", "cordeba", "common_voice")
    )
    has_dia = any(
        x in fuentes for x in ("callhome", "uba_games_figshare")
    )

    componente = (
        "todos" if has_asr and has_dia
        else "asr" if has_asr
        else "diarizacion"
    )
    nombres = [
        n for n in ARCHIVOS
        if componente == "todos"
        or n.startswith("asr_") == (componente == "asr")
    ]

    tablas = {
        nombre: _tabla(nombre, frames[nombre])
        for nombre in nombres
    }

    errores = validar_tablas(tablas, componente)
    if errores:
        raise ValueError(
            "Muestra normalizada inválida: "
            + json.dumps(errores[:8], ensure_ascii=False)
        )

    destino.parent.mkdir(parents=True, exist_ok=True)

    # Construir y validar todos los resultados antes de publicarlos.
    with tempfile.TemporaryDirectory(
        prefix="normalizado-build-",
        dir=destino.parent,
    ) as tmp:
        temporal = Path(tmp) / "normalizado"
        temporal.mkdir()

        for nombre in nombres:
            ruta = temporal / ARCHIVOS[nombre]
            if ruta.suffix == ".parquet":
                tablas[nombre].to_parquet(
                    ruta,
                    index=False,
                    compression="zstd",
                )
            else:
                tablas[nombre].to_csv(ruta, index=False)

            resultados[nombre] = {
                "filas": len(tablas[nombre]),
                "sha256": hashlib.sha256(
                    ruta.read_bytes()
                ).hexdigest(),
            }

        reportes = {}
        if anomalías_callhome is not None:
            politica = (
                "Excluir de los segmentos puntuables únicamente intervalos "
                "con tiempos finitos que incumplen 0 <= inicio < fin; "
                "preservar originales y localización en este informe"
            )
            reporte = {
                "fuente": "talkbank/callhome",
                "politica": politica,
                "cantidad": len(anomalías_callhome),
                "anomalias": anomalías_callhome,
            }
            informe = temporal / "ANOMALIAS_CALLHOME.json"
            informe.write_text(
                json.dumps(
                    reporte, ensure_ascii=False, indent=2, sort_keys=True,
                    allow_nan=False,
                ) + "\n",
                encoding="utf-8",
            )
            reportes["callhome"] = {
                "archivo": informe.name,
                "cantidad": len(anomalías_callhome),
                "sha256": hashlib.sha256(informe.read_bytes()).hexdigest(),
                "politica": politica,
                "origen": "talkbank/callhome:Parquet",
            }

        manifiesto = {
            "schema_version": SCHEMA_VERSION,
            "fuentes": resumen,
            "tablas": resultados,
            "reportes_anomalias": reportes,
            "estado": "validado_estructuralmente_no_evaluado",
        }

        (temporal / "MANIFIESTO_NORMALIZADO.json").write_text(
            json.dumps(
                manifiesto,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )

        # Comprobar también los archivos serializados.
        releidas = {}
        for nombre in nombres:
            ruta = temporal / ARCHIVOS[nombre]
            releidas[nombre] = (
                pd.read_parquet(ruta)
                if ruta.suffix == ".parquet"
                else pd.read_csv(
                    ruta,
                    keep_default_na=False,
                    na_values=[""],
                )
            )

        errores = validar_tablas(releidas, componente)
        if errores:
            raise ValueError(
                "Tablas serializadas inválidas: "
                + json.dumps(errores[:8], ensure_ascii=False)
            )

        copia_previa = Path(tmp) / "anterior"
        if destino.exists():
            destino.rename(copia_previa)

        try:
            temporal.rename(destino)
        except BaseException:
            if copia_previa.exists():
                copia_previa.rename(destino)
            raise

    return manifiesto