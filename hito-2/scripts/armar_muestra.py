#!/usr/bin/env python3
"""Arma la muestra del Hito 2 (hito-2/muestra/) a partir de las fuentes crudas.

Alcance: producto en castellano, evaluado por módulo.

Uso (desde la raíz del repo, después de `descargar_fuentes.py`):
    .venv/bin/python -I hito-2/scripts/armar_muestra.py

Determinístico (semilla fija). No usa la red. Necesita `ffprobe` (ffmpeg).

  Transcripción (castellano rioplatense)
    slr61/        Todas las transcripciones, índice de todo el audio y 1 clip
                  por hablante (44, FLAC, sin versionar).
    cordeba/      Índice de las 24 grabaciones y sus turnos. Sin audio.
    humyn/        Índice de las 28 grabaciones y turnos de las 6 en castellano.
                  Sin audio.
  Separación de hablantes
    ami/, icsi/   Turnos con hablante, tiempos y texto; participantes; índice
                  del audio de cada reunión; de 24 extractos de 30 s, la
                  energía por cuadro (el audio queda en disco, sin versionar).
    voxconverse/  Quién habla cuándo en las 448 sesiones (RTTM).
  Minuta
    ami/          Minuta de referencia de las 142 reuniones que la tienen
                  (minutas.parquet) y los fragmentos de la transcripción que
                  respaldan cada ítem (evidencias.parquet).
"""
from __future__ import annotations

import hashlib
import io
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
import soundfile as sf
from lxml import etree

# El modo aislado (-I) no incorpora el directorio del script a sys.path.
SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from validar_muestra import TOLERANCIA_FIN_FIGSHARE_S

SEMILLA = 20261010
HITO = Path(__file__).resolve().parent.parent
CACHE = HITO / ".cache"
OUT = HITO / "muestra"
NITE = "{http://nite.sourceforge.net/}"
PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
HREF = re.compile(r"^(?P<archivo>[^#]+)#id\((?P<a>[^)]+)\)(?:\.\.id\((?P<b>[^)]+)\))?$")


def xml(z: zipfile.ZipFile, nombre: str):
    return etree.fromstring(z.read(nombre), PARSER)


def num(s: str | None) -> float | None:
    try:
        return float(s) if s not in (None, "") else None
    except ValueError:
        return None


def guardar(df: pd.DataFrame, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if ruta.suffix == ".parquet":
        df.to_parquet(ruta, index=False, compression="zstd")
    else:
        df.to_csv(ruta, index=False)
    print(f"  {ruta.relative_to(HITO)}  {len(df):>7} filas  {ruta.stat().st_size / 1e6:6.2f} MB")


class Palabras:
    """Índice de un archivo *.words.xml: orden, texto y tiempos de cada elemento."""

    def __init__(self, raiz, es_palabra):
        self.pos: dict[str, int] = {}
        self.items: list[tuple[bool, bool, str]] = []
        self.tiempos: list[tuple[float | None, float | None]] = []
        self.total = self.sin_tiempo = 0
        for i, e in enumerate(raiz):
            self.pos[e.get(NITE + "id")] = i
            palabra, puntuacion = es_palabra(e)
            self.items.append((palabra, puntuacion, (e.text or "").strip()))
            self.tiempos.append((num(e.get("starttime")), num(e.get("endtime"))) if palabra else (None, None))
            if palabra:
                self.total += 1
                self.sin_tiempo += num(e.get("starttime")) is None or num(e.get("endtime")) is None

    def tramo(self, a: str, b: str | None) -> tuple[str, int]:
        """Texto y cantidad de palabras del rango [a, b]."""
        if a not in self.pos:
            return "", 0
        i, j = self.pos[a], self.pos.get(b or a, self.pos[a])
        partes, n = [], 0
        for palabra, puntuacion, texto in self.items[i:j + 1]:
            if not (palabra or puntuacion) or not texto:
                continue
            if puntuacion and partes:
                partes[-1] += texto
            else:
                partes.append(texto)
            n += palabra
        return " ".join(partes), n


def intervalo(palabras: Palabras, a: str, b: str | None) -> tuple[float | None, float | None]:
    """Inicio y fin del rango [a, b], según los tiempos de sus palabras."""
    if a not in palabras.pos:
        return None, None
    tramo = palabras.tiempos[palabras.pos[a]:palabras.pos.get(b or a, palabras.pos[a]) + 1]
    inicios, fines = [t0 for t0, _ in tramo if t0 is not None], [t1 for _, t1 in tramo if t1 is not None]
    return (min(inicios) if inicios else None), (max(fines) if fines else None)


def ami_es_palabra(e):
    if e.tag != "w":
        return False, False
    return (e.get("punc") != "true"), (e.get("punc") == "true")


# Clases de token de ICSI que no cuentan como palabra (puntuación, posesivo, guion, símbolo).
ICSI_PUNT = {".", "CM", "QUOTE", "LQUOTE", "RQUOTE", "HYPH", "APOSS", "SYM"}


def icsi_es_palabra(e):
    if e.tag != "w":
        return False, False
    c = e.get("c") or "W"
    return (c not in ICSI_PUNT), (c in ICSI_PUNT)


def turnos_nxt(z, archivos, palabras_de, fila_de):
    """Recorre los archivos de segmentos y arma una fila por turno."""
    filas = []
    for n in archivos:
        reunion, agente = Path(n).name.split(".")[:2]
        for seg in xml(z, n).iter("segment"):
            texto, k = [], 0
            for h in seg.findall(NITE + "child"):
                m = HREF.match(h.get("href"))
                if m:
                    t, c = palabras_de(reunion, agente).tramo(m["a"], m["b"])
                    texto.append(t)
                    k += c
            filas.append({"reunion": reunion, "agente": agente, **fila_de(reunion, agente, seg),
                          "n_palabras": k, "texto": " ".join(t for t in texto if t)})
    return pd.DataFrame(filas).sort_values(["reunion", "inicio"], na_position="last")


def columnas_de_audio(reuniones: pd.DataFrame, indice: dict) -> pd.DataFrame:
    """Suma a cada reunión lo que dijo el servidor sobre su audio."""
    cols = {"audio_disponible": "disponible", "audio_bytes": "bytes", "audio_hz": "hz",
            "audio_canales": "canales", "audio_bits": "bits", "audio_duracion_s": "duracion_s",
            "audio_url": "url"}
    for destino, origen in cols.items():
        reuniones[destino] = [indice.get(r, {}).get(origen) for r in reuniones["reunion"]]
    reuniones["audio_disponible"] = reuniones["audio_disponible"].fillna(False).astype(bool)
    return reuniones


PASO_ENERGIA = 0.02   # segundos por cuadro


def extractos(corpus: str, plan: list[dict]) -> pd.DataFrame:
    """Extractos de 30 s: guarda el audio en FLAC (no se versiona) y su energía por cuadro (sí).

    La energía por cuadro de 20 ms alcanza para cotejar los tiempos anotados contra el audio
    sin tener el audio en el repo.
    """
    destino = OUT / corpus / "extractos"
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    filas, energia = [], []
    for p in (p for p in plan if p["corpus"] == corpus):
        datos, hz = sf.read(CACHE / "audio" / "extractos" / f"{p['reunion']}.wav", dtype="int16", always_2d=True)
        archivo = f"{p['reunion']}.flac"
        sf.write(destino / archivo, datos, hz, format="FLAC", subtype="PCM_16")
        filas.append({"reunion": p["reunion"], "archivo": f"extractos/{archivo}", "inicio_s": p["inicio_s"],
                      "duracion_s": p["duracion_s"], "frecuencia_hz": hz, "canales": datos.shape[1]})
        n = int(hz * PASO_ENERGIA)
        mono = datos.astype("float32").mean(axis=1) / 32768
        rms = ((mono[: len(mono) // n * n].reshape(-1, n) ** 2).mean(axis=1)) ** 0.5
        energia += [{"reunion": p["reunion"], "cuadro": k, "energia": float(e)} for k, e in enumerate(rms)]
    guardar(pd.DataFrame(energia).astype({"energia": "float32"}), OUT / corpus / "extractos_energia.parquet")
    return pd.DataFrame(filas)


# Secciones de la minuta abstractiva de AMI y el nombre que reciben en la muestra.
MINUTA_TIPOS = {"abstract": "resumen", "actions": "accion", "decisions": "decision", "problems": "problema"}


def minutas_ami(z: zipfile.ZipFile) -> pd.DataFrame:
    """Una fila por frase de la minuta de referencia: reunión, sección, orden y texto."""
    filas = []
    for n in sorted(x for x in z.namelist() if x.startswith("abstractive/") and x.endswith(".abssumm.xml")):
        reunion = Path(n).name.split(".")[0]
        orden = {t: 0 for t in MINUTA_TIPOS.values()}
        for seccion in xml(z, n):
            tipo = MINUTA_TIPOS.get(seccion.tag)
            for frase in seccion.iter("sentence") if tipo else ():
                orden[tipo] += 1
                filas.append({"reunion": reunion, "tipo": tipo, "orden": orden[tipo],
                              "item_id": frase.get(NITE + "id"), "texto": " ".join((frase.text or "").split())})
    return pd.DataFrame(filas)


def evidencias_ami(z: zipfile.ZipFile, palabras_de, hablante_global: dict) -> pd.DataFrame:
    """Una fila por fragmento de la transcripción que respalda un ítem de la minuta.

    AMI enlaza cada frase de la minuta con los actos de diálogo que la respaldan (summlink).
    """
    actos: dict[str, dict] = {}

    def acto(archivo: str, id_acto: str) -> dict | None:
        if archivo not in actos:
            actos[archivo] = {}
            reunion, agente = archivo.split(".")[:2]
            try:
                raiz = xml(z, "dialogueActs/" + archivo)
            except KeyError:
                return None
            for d in raiz.iter("dact"):
                textos, ini, fin = [], None, None
                for h in d.findall(NITE + "child"):
                    m = HREF.match(h.get("href"))
                    if not m:
                        continue
                    pal = palabras_de(reunion, agente)
                    textos.append(pal.tramo(m["a"], m["b"])[0])
                    a, b = intervalo(pal, m["a"], m["b"])
                    ini = a if ini is None else ini
                    fin = b if b is not None else fin
                actos[archivo][d.get(NITE + "id")] = {
                    "hablante": hablante_global.get((reunion, agente)), "inicio": ini, "fin": fin,
                    "texto": " ".join(t for t in textos if t)}
        return actos[archivo].get(id_acto)

    filas, vistos = [], set()
    for n in sorted(x for x in z.namelist() if x.endswith(".summlink.xml")):
        reunion = Path(n).name.split(".")[0]
        for link in xml(z, n).iter("summlink"):
            ext = item = None
            for p in link.findall(NITE + "pointer"):
                m = HREF.match(p.get("href"))
                if m and p.get("role") == "extractive":
                    ext = (m["archivo"], m["a"])
                elif m and p.get("role") == "abstractive":
                    item = m["a"]
            if not (ext and item) or (item, ext) in vistos:
                continue
            vistos.add((item, ext))
            a = acto(*ext)
            if a:
                filas.append({"reunion": reunion, "item_id": item, "acto_id": ext[1], **a})
    return pd.DataFrame(filas)


def armar_ami(indice: dict, plan: list[dict]) -> dict:
    print("[ami]")
    z = zipfile.ZipFile(CACHE / "ami" / "ami_public_manual_1.6.2.zip")
    nombres = set(z.namelist())
    particion = {r: p for p in ("train", "dev", "test")
                 for r in (CACHE / "pyannote_ami" / f"{p}.meetings.txt").read_text().split()}

    reuniones, hablante_global = [], {}
    for m in xml(z, "corpusResources/meetings.xml").findall("meeting"):
        rid = m.get("observation")
        sp = m.findall("speaker")
        for s in sp:
            hablante_global[(rid, s.get("nxt_agent"))] = s.get("global_name")
        fecha = m.get("dateOnly") or ""
        anio = fecha.split("-")[-1] if fecha else ""
        reuniones.append({
            "reunion": rid, "serie": rid[:-1], "tipo": m.get("type"),
            "fecha_cruda": fecha, "anio": int("20" + anio[-2:]) if anio else None,
            "duracion_s": num(m.get("duration")), "n_hablantes": len(sp),
            "hablantes": ";".join(sorted(s.get("global_name") or "" for s in sp)),
            "particion_oficial": m.get("seen_type") or m.get("visibility") or "",
            # Partición que usa pyannote para entrenar y evaluar su modelo con AMI.
            "particion_pyannote": particion.get(rid, ""),
        })
    reuniones = pd.DataFrame(reuniones).sort_values("reunion")

    participantes = pd.DataFrame([{
        "hablante": p.get(NITE + "id"), "sexo": p.get("sex"),
        "edad": num(p.get("age_at_collection")), "lengua_nativa": p.get("native_language"),
    } for p in xml(z, "corpusResources/participants.xml").findall("participant")])

    indice_palabras: dict[tuple[str, str], Palabras] = {}

    def palabras_de(reunion, agente):
        if (reunion, agente) not in indice_palabras:
            indice_palabras[(reunion, agente)] = Palabras(
                xml(z, f"words/{reunion}.{agente}.words.xml"), ami_es_palabra)
        return indice_palabras[(reunion, agente)]

    turnos = turnos_nxt(
        z, sorted(x for x in nombres if x.startswith("segments/") and x.endswith(".xml")), palabras_de,
        lambda r, a, seg: {"hablante": hablante_global.get((r, a)),
                           "inicio": num(seg.get("transcriber_start")), "fin": num(seg.get("transcriber_end"))})

    conteo = pd.DataFrame([{"reunion": r, "palabras": p.total, "palabras_sin_tiempo": p.sin_tiempo}
                           for (r, _), p in indice_palabras.items()]).groupby("reunion").sum().reset_index()
    reuniones = columnas_de_audio(reuniones.merge(conteo, on="reunion", how="left"), indice)

    minutas = minutas_ami(z)
    evidencias = evidencias_ami(z, palabras_de, hablante_global)
    minutas["n_evidencias"] = minutas["item_id"].map(evidencias.groupby("item_id").size()).fillna(0).astype(int)
    reuniones["tiene_minuta"] = reuniones["reunion"].isin(minutas["reunion"])
    reuniones["tiene_evidencias"] = reuniones["reunion"].isin(evidencias["reunion"])

    guardar(reuniones, OUT / "ami" / "reuniones.csv")
    guardar(participantes, OUT / "ami" / "participantes.csv")
    guardar(turnos, OUT / "ami" / "turnos.parquet")
    guardar(minutas, OUT / "ami" / "minutas.parquet")
    guardar(evidencias, OUT / "ami" / "evidencias.parquet")
    guardar(extractos("ami", plan), OUT / "ami" / "extractos.csv")
    return {"reuniones": len(reuniones), "reuniones_con_minuta": int(reuniones["tiene_minuta"].sum()),
            "items_de_minuta": len(minutas)}


def armar_icsi(indice: dict, plan: list[dict]) -> dict:
    print("[icsi]")
    z = zipfile.ZipFile(CACHE / "icsi" / "ICSI_plus_NXT.zip")
    nombres = set(z.namelist())
    P = "ICSIplus/"

    hablantes = []
    for s in xml(z, P + "speakers.xml").findall("speaker"):
        lengua = s.find("language")
        hablantes.append({
            "hablante": s.get("tag"), "genero": s.get("gender"),
            "edad": num((s.findtext("age") or "").strip() or None),
            "educacion": (s.findtext("education") or "").strip(),
            "nativo_ingles": lengua is not None and lengua.find("native") is None,
            "fecha_formulario": s.get("formdate"),
        })
    hablantes = pd.DataFrame(hablantes)

    indice_palabras: dict[tuple[str, str], Palabras] = {}

    def palabras_de(reunion, agente):
        if (reunion, agente) not in indice_palabras:
            indice_palabras[(reunion, agente)] = Palabras(
                xml(z, f"{P}Words/{reunion}.{agente}.words.xml"), icsi_es_palabra)
        return indice_palabras[(reunion, agente)]

    turnos = turnos_nxt(
        z, sorted(x for x in nombres if x.startswith(P + "Segments/") and x.endswith(".xml")), palabras_de,
        lambda r, a, seg: {"hablante": seg.get("participant"),
                           "inicio": num(seg.get("starttime")), "fin": num(seg.get("endtime")),
                           # ICSI incluye una tarea de lectura de dígitos que no es conversación
                           "lectura_de_digitos": seg.get("digittask") is not None})

    g = turnos.groupby("reunion")
    reuniones = pd.DataFrame({
        "reunion": g.size().index,
        "grupo": [r[:3] for r in g.size().index],
        "duracion_s": g["fin"].max().values,
        "n_hablantes": g["hablante"].nunique().values,
        "hablantes": g["hablante"].agg(lambda s: ";".join(sorted(set(s.dropna())))).values,
    })
    conteo = pd.DataFrame([{"reunion": r, "palabras": p.total, "palabras_sin_tiempo": p.sin_tiempo}
                           for (r, _), p in indice_palabras.items()]).groupby("reunion").sum().reset_index()
    reuniones = columnas_de_audio(reuniones.merge(conteo, on="reunion", how="left"), indice)

    guardar(reuniones, OUT / "icsi" / "reuniones.csv")
    guardar(hablantes, OUT / "icsi" / "hablantes.csv")
    guardar(turnos, OUT / "icsi" / "turnos.parquet")
    guardar(extractos("icsi", plan), OUT / "icsi" / "extractos.csv")
    return {"reuniones": len(reuniones)}


def armar_voxconverse(indice: dict) -> dict:
    print("[voxconverse]")
    z = zipfile.ZipFile(CACHE / "voxconverse" / "voxconverse-master.zip")
    filas = []
    for n in sorted(x for x in z.namelist() if x.endswith(".rttm")):
        particion = Path(n).parent.name
        for linea in z.read(n).decode().splitlines():
            c = linea.split()
            if len(c) >= 8 and c[0] == "SPEAKER":
                filas.append({"particion": particion, "sesion": c[1], "hablante": c[7],
                              "inicio": float(c[3]), "duracion": float(c[4])})
    df = pd.DataFrame(filas)
    guardar(df, OUT / "voxconverse" / "rttm.parquet")
    audio = pd.DataFrame([{"particion": p, "audio_url": f.get("url"),
                           "audio_disponible": bool(f.get("disponible")), "audio_bytes": f.get("bytes")}
                          for p, f in indice.items()])
    guardar(audio, OUT / "voxconverse" / "audio.csv")
    return {"sesiones": int(df["sesion"].nunique())}


def armar_slr61() -> dict:
    """OpenSLR 61: transcripciones, índice de todo el audio y 1 clip por hablante."""
    print("[slr61]")
    src = CACHE / "slr61"
    tr = []
    for genero in ("female", "male"):
        for linea in (src / f"line_index_{genero}.tsv").read_text(encoding="utf8").splitlines():
            archivo, _, texto = linea.partition("\t")
            tr.append({"archivo": archivo.strip(), "genero": genero,
                       "hablante": "_".join(archivo.split("_")[:2]), "texto": texto.strip()})
    tr = pd.DataFrame(tr)

    manifiesto, crudos = [], {}
    for genero in ("female", "male"):
        z = zipfile.ZipFile(src / f"es_ar_{genero}.zip")
        for info in z.infolist():
            if not info.filename.lower().endswith(".wav"):
                continue
            fila = {"archivo": Path(info.filename).stem, "bytes": info.file_size, "legible": True}
            try:
                datos, hz = sf.read(io.BytesIO(z.read(info)), dtype="int16", always_2d=True)
                fila |= {"frecuencia_hz": hz, "canales": datos.shape[1], "duracion_s": round(len(datos) / hz, 4),
                         "pico": float(abs(datos.astype("int32")).max() / 32768)}
            except Exception as e:  # audio roto: se registra
                fila |= {"legible": False, "error": repr(e)[:120]}
            manifiesto.append(fila)
            crudos[fila["archivo"]] = (z, info)
    manifiesto = pd.DataFrame(manifiesto)

    rng = random.Random(SEMILLA)
    clips = OUT / "slr61" / "clips"
    if clips.exists():
        shutil.rmtree(clips)
    clips.mkdir(parents=True)
    elegidos = []
    for _, grupo in sorted(tr[tr["archivo"].isin(crudos)].groupby("hablante"), key=lambda kv: kv[0]):
        archivo = rng.choice(sorted(grupo["archivo"]))
        z, info = crudos[archivo]
        datos, hz = sf.read(io.BytesIO(z.read(info)), dtype="int16")
        sf.write(clips / f"{archivo}.flac", datos, hz, format="FLAC", subtype="PCM_16")
        elegidos.append(archivo)
    tr["en_muestra_de_audio"] = tr["archivo"].isin(elegidos)

    guardar(tr, OUT / "slr61" / "transcripciones.csv")
    guardar(manifiesto, OUT / "slr61" / "manifiesto_audio.csv")
    print(f"  slr61/clips/  {len(elegidos)} clips FLAC  {sum(f.stat().st_size for f in clips.iterdir()) / 1e6:.2f} MB")
    return {"clips": len(tr), "clips_en_muestra": len(elegidos)}


def ffprobe(ruta: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_name,sample_rate,channels", "-of", "json", str(ruta)],
                       capture_output=True, text=True, timeout=120)
    try:
        j = json.loads(r.stdout or "{}")
        st = (j.get("streams") or [{}])[0]
        return {"legible": bool(j.get("format", {}).get("duration")),
                "duracion_s": num(j.get("format", {}).get("duration")), "codec": st.get("codec_name"),
                "frecuencia_hz": num(st.get("sample_rate")), "canales": st.get("channels")}
    except json.JSONDecodeError:
        return {"legible": False}


def a_segundos(marca: str) -> float | None:
    try:
        h, m, s = marca.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except (ValueError, AttributeError):
        return None


def n_palabras(texto: str) -> int:
    return len(re.findall(r"[^\W\d_]+", texto or ""))


def armar_humyn() -> dict:
    """Humyn LATAM: índice de las 28 grabaciones y turnos de las que están en castellano."""
    import pyarrow.parquet as pq
    print("[humyn]")
    grabaciones, turnos = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for f in sorted((CACHE / "humyn").glob("*.parquet")):
            for lote in pq.ParquetFile(f).iter_batches(batch_size=1):
                fila = lote.to_pylist()[0]
                audio = Path(tmp) / "audio.bin"
                audio.write_bytes(fila["audio"]["bytes"])
                crudo = fila["transcript_json"] or ""
                try:  # la ficha promete JSON con turnos; no todas las filas lo cumplen
                    trans, con_turnos = json.loads(crudo), True
                except json.JSONDecodeError:
                    trans, con_turnos = [{"speaker": None, "text": crudo}], False
                grabaciones.append({
                    "archivo": fila["file_name"], "idioma": fila["language"], "tipo": fila["type"],
                    **ffprobe(audio), "transcripcion_con_turnos": con_turnos,
                    "transcripcion_sha1": hashlib.sha1(crudo.encode()).hexdigest()[:12],
                    "n_turnos": len(trans), "n_hablantes": len({t.get("speaker") for t in trans}),
                    "n_palabras": sum(n_palabras(t.get("text", "")) for t in trans),
                })
                if fila["language"].lower().startswith("spanish"):
                    for i, t in enumerate(trans):
                        turnos.append({"archivo": fila["file_name"], "idioma": fila["language"], "orden": i,
                                       "hablante": t.get("speaker"), "inicio": a_segundos(t.get("start")),
                                       "fin": a_segundos(t.get("end")), "texto": t.get("text", "")})
    guardar(pd.DataFrame(grabaciones), OUT / "humyn" / "grabaciones.csv")
    guardar(pd.DataFrame(turnos), OUT / "humyn" / "turnos.parquet")
    return {"grabaciones": len(grabaciones)}


def armar_cordeba() -> dict:
    """CORdeBA: índice de las 24 grabaciones y sus turnos (sin tiempos)."""
    print("[cordeba]")
    src = CACHE / "cordeba"
    grabaciones, turnos = [], []
    for _, fila in pd.read_csv(src / "metadata.csv").iterrows():
        archivo = Path(fila["file_name"]).name
        try:
            trans = json.loads(fila["text"])
        except (TypeError, json.JSONDecodeError):
            trans = []
        ruta = src / archivo
        grabaciones.append({"archivo": archivo, "bytes": ruta.stat().st_size, **ffprobe(ruta),
                            "n_turnos": len(trans), "n_hablantes": len({t.get("speaker") for t in trans}),
                            "n_palabras": sum(n_palabras(t.get("text", "")) for t in trans)})
        for i, t in enumerate(trans):
            turnos.append({"archivo": archivo, "orden": i, "hablante": str(t.get("speaker")),
                           "texto": t.get("text", "")})
    guardar(pd.DataFrame(grabaciones), OUT / "cordeba" / "grabaciones.csv")
    guardar(pd.DataFrame(turnos), OUT / "cordeba" / "turnos.parquet")
    return {"grabaciones": len(grabaciones)}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        while b := f.read(1 << 20):
            h.update(b)
    return h.hexdigest()


# La lectura de RAR y ZIP es compartida por los adaptadores, sin extracción permanente.
def entradas_comprimidas(ruta: Path, *, incluir=None):
    """Itera (nombre, flujo) sobre las entradas regulares de un archivo.

    Si `incluir` descarta una entrada, entrega (nombre, None) sin solicitar
    su contenido descomprimido; su nombre sigue disponible para procedencia.
    Se usa libarchive y un archivo temporal para datos mayores de 8 MiB.
    """
    import ctypes as ct
    from ctypes.util import find_library

    nombre_biblioteca = find_library("archive")
    if not nombre_biblioteca:
        raise RuntimeError("Se requiere libarchive (en Ubuntu: libarchive13)")
    biblioteca = ct.CDLL(nombre_biblioteca)
    prototipos = {
        "archive_read_new": ([], ct.c_void_p),
        "archive_read_support_format_all": ([ct.c_void_p], ct.c_int),
        "archive_read_support_filter_all": ([ct.c_void_p], ct.c_int),
        "archive_read_open_filename": ([ct.c_void_p, ct.c_char_p, ct.c_size_t], ct.c_int),
        "archive_read_next_header": ([ct.c_void_p, ct.POINTER(ct.c_void_p)], ct.c_int),
        "archive_entry_pathname": ([ct.c_void_p], ct.c_char_p),
        "archive_entry_filetype": ([ct.c_void_p], ct.c_uint),
        "archive_read_data": ([ct.c_void_p, ct.c_void_p, ct.c_size_t], ct.c_ssize_t),
        "archive_read_data_skip": ([ct.c_void_p], ct.c_int),
        "archive_error_string": ([ct.c_void_p], ct.c_char_p),
        "archive_read_free": ([ct.c_void_p], ct.c_int),
    }
    for nombre, (argumentos, resultado) in prototipos.items():
        funcion = getattr(biblioteca, nombre)
        funcion.argtypes, funcion.restype = argumentos, resultado

    lector = biblioteca.archive_read_new()
    if not lector:
        raise RuntimeError("libarchive no pudo inicializarse")
    try:
        biblioteca.archive_read_support_format_all(lector)
        biblioteca.archive_read_support_filter_all(lector)
        if biblioteca.archive_read_open_filename(lector, str(ruta).encode(), 10240) != 0:
            raise ValueError(f"No se pudo abrir {ruta}")
        entrada = ct.c_void_p()
        bloque = ct.create_string_buffer(1024 * 1024)
        while True:
            estado = biblioteca.archive_read_next_header(lector, ct.byref(entrada))
            if estado == 1:  # ARCHIVE_EOF
                break
            if estado != 0:
                raise ValueError(f"Cabecera dañada en {ruta}: {estado}")
            nombre = biblioteca.archive_entry_pathname(entrada).decode("utf-8")
            partes = Path(nombre.replace("\\", "/"))
            if partes.is_absolute() or ".." in partes.parts:
                raise ValueError(f"Ruta interna no permitida: {nombre}")
            tipo = biblioteca.archive_entry_filetype(entrada)
            if tipo == 0o040000:  # directorio
                continue
            if tipo != 0o100000:
                raise ValueError(f"Tipo de entrada no admitido: {nombre}")
            if incluir is not None and not incluir(nombre):
                estado_omision = biblioteca.archive_read_data_skip(lector)
                if estado_omision != 0:
                    detalle = biblioteca.archive_error_string(lector)
                    mensaje = detalle.decode("utf-8", "replace") if detalle else "sin detalle"
                    raise ValueError(
                        f"No se pudo omitir la entrada auxiliar {nombre}: "
                        f"libarchive={estado_omision}: {mensaje}"
                    )
                yield nombre, None
                continue
            with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as temporal:
                while True:
                    cantidad = biblioteca.archive_read_data(lector, bloque, len(bloque))
                    if cantidad == 0:
                        break
                    if cantidad < 0:
                        detalle = biblioteca.archive_error_string(lector)
                        mensaje = detalle.decode("utf-8", "replace") if detalle else "sin detalle"
                        raise ValueError(
                            f"Error leyendo {nombre}: libarchive={cantidad}: {mensaje}"
                        )
                    temporal.write(bloque.raw[:cantidad])
                temporal.seek(0)
                yield nombre, temporal
    finally:
        biblioteca.archive_read_free(lector)


_UBA_ARCHIVO = re.compile(r"s(\d+)\.objects\.(\d+)\.channel([12])\.(phrases|wav)\Z", re.I)


def _uba_identidad(nombre: str, extension: str):
    ruta_interna = Path(nombre.replace("\\", "/"))

    # Los WAV de este directorio no están separados por hablante.
    # Se registran como auxiliares y no se asignan a ningún canal.
    if extension == "wav" and any(
        parte.casefold() == "sin separar canales"
        for parte in ruta_interna.parts
    ):
        return None

    coincidencia = _UBA_ARCHIVO.fullmatch(ruta_interna.name)
    if coincidencia is None:
        if nombre.lower().endswith(f".{extension}"):
            raise ValueError(f"Nombre inesperado en UBA Games: {nombre}")
        return None
    if coincidencia[4].lower() != extension:
        raise ValueError(f"Tipo incompatible: {nombre}")
    sesion = f"S{int(coincidencia[1])}"
    tarea = f"{int(coincidencia[2]):02d}"
    canal = int(coincidencia[3])
    return sesion, tarea, canal


def _uba_grabacion(sesion: str, tarea: str) -> str:
    return f"figshare_v2_{sesion}_objects_{tarea}"


def armar_uba_games_figshare() -> dict:
    """Prepara datos de diarización de Figshare v2; no emite un veredicto."""
    import tomllib
    import wave
    import numpy as np

    print("[uba_games_figshare]")
    cfg = tomllib.loads((HITO / "fuentes.toml").read_text(encoding="utf-8"))["uba_games_figshare"]
    lock = json.loads((HITO / "fuentes.lock.json").read_text(encoding="utf-8"))
    raiz = CACHE / "uba_games" / "figshare-v2"
    rutas = {}
    for nombre, ficha in cfg["archivos"].items():
        ruta = raiz / nombre
        clave = f"uba_games/figshare-v2/{nombre}"
        if not ruta.is_file() or ruta.stat().st_size != ficha["bytes"]:
            raise ValueError(f"Falta original o tamaño oficial incorrecto: {clave}")
        sha = sha256(ruta)
        if lock.get("archivos", {}).get(clave) != {"bytes": ficha["bytes"], "sha256": sha}:
            raise ValueError(f"Original no fijado correctamente: {clave}")
        resumen = hashlib.md5()
        with ruta.open("rb") as f:
            for bloque in iter(lambda: f.read(1024 * 1024), b""):
                resumen.update(bloque)
        if resumen.hexdigest() != ficha["md5"]:
            raise ValueError(f"Original diferente al publicado por Figshare: {clave}")
        rutas[nombre] = ruta

    intervalos = []
    referencias = defaultdict(dict)
    auxiliares = {"phrases": [], "wavs": []}
    for nombre, contenido in entradas_comprimidas(rutas["phrases.rar"]):
        identidad = _uba_identidad(nombre, "phrases")
        if identidad is None:
            auxiliares["phrases"].append(nombre)
            continue
        sesion, tarea, canal = identidad
        clave = (sesion, tarea)
        if canal in referencias[clave]:
            raise ValueError(f"Canal de anotación duplicado: {nombre}")
        anterior = 0.0
        cantidad = 0
        for numero, linea in enumerate(contenido.read().decode("utf-8-sig").splitlines(), 1):
            campos = linea.split("\t", 2)
            if len(campos) != 3 or not campos[2].strip():
                raise ValueError(f"Anotación mal formada: {nombre}:{numero}")
            inicio, fin = float(campos[0]), float(campos[1])
            if not (np.isfinite(inicio) and np.isfinite(fin) and 0 <= inicio < fin):
                raise ValueError(f"Tiempos inválidos: {nombre}:{numero}")
            if inicio < anterior - 1e-4:
                raise ValueError(f"Tiempos desordenados: {nombre}:{numero}")
            texto = campos[2].strip()
            intervalos.append({
                "fuente": "uba_games_figshare", "session_id": f"figshare_v2_{sesion}",
                "recording_id": _uba_grabacion(sesion, tarea),
                "speaker_id": f"figshare_v2_{sesion}_canal{canal}",
                "canal": canal, "orden": numero, "inicio_s": inicio, "fin_s": fin,
                "texto_original": texto, "silencio_marcado": texto == "#",
                "origen_anotacion": nombre,
            })
            anterior = fin
            cantidad += 1
        if cantidad == 0:
            raise ValueError(f"Anotación vacía: {nombre}")
        referencias[clave][canal] = {"fin_s": anterior, "archivo": nombre}

    # Se selecciona determinísticamente la primera tarea de cada sesión.
    # Los extractos acústicos son derivados, no forman parte de las referencias.
    primeras = {}
    for sesion, tarea in sorted(referencias):
        primeras.setdefault(sesion, tarea)
    audios = defaultdict(dict)
    fragmentos = defaultdict(dict)
    for nombre, contenido in entradas_comprimidas(
        rutas["wavs.rar"],
        incluir=lambda nombre: _uba_identidad(nombre, "wav") is not None,
    ):
        identidad = _uba_identidad(nombre, "wav")
        if identidad is None:
            auxiliares["wavs"].append(nombre)
            continue
        sesion, tarea, canal = identidad
        clave = (sesion, tarea)
        if canal in audios[clave]:
            raise ValueError(f"Canal WAV duplicado: {nombre}")
        try:
            with wave.open(contenido, "rb") as audio:
                hz, canales, ancho = audio.getframerate(), audio.getnchannels(), audio.getsampwidth()
                cuadros = audio.getnframes()
                compresion = audio.getcomptype()
                if min(hz, canales, ancho, cuadros) <= 0:
                    raise ValueError(f"WAV vacío o inválido: {nombre}")
                primer_tramo = None
                if primeras.get(sesion) == tarea and (canales, hz, ancho, compresion) == (1, 16000, 2, "NONE"):
                    primer_tramo = audio.readframes(min(cuadros, 30 * hz))
                # Inspección exhaustiva: una cabecera correcta no alcanza.
                # Si ya se leyó el extracto, se continúa desde esa posición.
                bytes_leidos = len(primer_tramo) if primer_tramo is not None else 0
                while datos := audio.readframes(65536):
                    bytes_leidos += len(datos)
                if bytes_leidos != cuadros * canales * ancho:
                    raise ValueError(f"WAV truncado: {nombre}")
        except (wave.Error, EOFError) as e:
            raise ValueError(f"Audio ilegible {nombre}: {e}") from e
        audios[clave][canal] = {
            "archivo": nombre, "duracion_s": cuadros / hz,
            "hz": hz, "canales": canales, "bytes_muestra": ancho,
            "compresion": compresion,
        }
        if primer_tramo is not None:
            fragmentos[clave][canal] = np.frombuffer(primer_tramo, dtype="<i2").copy()

    grabaciones, hablantes, extractos = [], [], []
    salida = OUT / "uba_games_figshare"
    carpeta_audio = salida / "audio_muestra"
    carpeta_audio.mkdir(parents=True, exist_ok=True)
    anomalías = []
    por_precision = []
    for sesion, tarea in sorted(set(referencias) | set(audios)):
        clave = (sesion, tarea)
        ref, audio = referencias.get(clave, {}), audios.get(clave, {})
        recording = _uba_grabacion(sesion, tarea)
        formatos = {(a["hz"], a["canales"], a["bytes_muestra"], a["compresion"]) for a in audio.values()}
        duraciones = [a["duracion_s"] for a in audio.values()]
        duracion = max(duraciones, default=None)
        completa = set(ref) == {1, 2} and set(audio) == {1, 2}
        alineacion = (abs(duraciones[0] - duraciones[1]) if len(duraciones) == 2 else None)
        excesos = {
            c: max(0.0, ref[c]["fin_s"] - audio[c]["duracion_s"])
            for c in ref.keys() & audio.keys()
        }
        exceso_max = max(excesos.values(), default=0.0)
        fuera = exceso_max > 0.0
        fuera_tolerancia = exceso_max > TOLERANCIA_FIN_FIGSHARE_S + 1e-12
        aceptada_por_precision = fuera and not fuera_tolerancia
        mismo_formato = len(formatos) == 1 and next(iter(formatos), None) == (16000, 1, 2, "NONE")
        valido_audio = completa and mismo_formato and alineacion <= 1 / 16000 and not fuera_tolerancia
        grabaciones.append({
            "fuente": "uba_games_figshare", "session_id": f"figshare_v2_{sesion}",
            "recording_id": recording, "group_id": f"figshare_v2_{sesion}",
            "tarea": tarea, "duracion_s": duracion,
            "canales_con_referencia": len(ref), "canales_con_audio": len(audio),
            "n_hablantes_referencia": len(ref), "audio_hz": 16000 if mismo_formato else None,
            "alineacion_canales_s": alineacion,
            "anotacion_fuera_del_audio": fuera,
            "exceso_terminal_max_s": exceso_max,
            "exceso_aceptado_por_precision": aceptada_por_precision,
            "exceso_superior_a_tolerancia": fuera_tolerancia,
            "par_audio_referencia_valido": bool(valido_audio),
            "origen": "figshare:22647313:v2", "source_split": None,
            "project_split": None,
        })
        if not valido_audio:
            anomalías.append(recording)
        if aceptada_por_precision and valido_audio:
            por_precision.append(recording)
        for canal in sorted(ref.keys() | audio.keys()):
            hablantes.append({"fuente": "uba_games_figshare", "session_id": f"figshare_v2_{sesion}",
                              "recording_id": recording, "speaker_id": f"figshare_v2_{sesion}_canal{canal}",
                              "canal": canal, "tiene_anotacion": canal in ref, "tiene_audio": canal in audio,
                              "archivo_anotacion": ref.get(canal, {}).get("archivo"),
                              "archivo_audio": audio.get(canal, {}).get("archivo")})
        if valido_audio and primeras.get(sesion) == tarea and set(fragmentos.get(clave, {})) == {1, 2}:
            a, b = fragmentos[clave][1], fragmentos[clave][2]
            largo = max(len(a), len(b))
            mezcla = np.zeros(largo, dtype=np.int32)
            mezcla[:len(a)] += a.astype(np.int32)
            mezcla[:len(b)] += b.astype(np.int32)
            mezcla = np.floor_divide(mezcla, 2).astype(np.int16)
            archivo = f"{recording}.flac"
            sf.write(carpeta_audio / archivo, mezcla, 16000, format="FLAC", subtype="PCM_16")
            extractos.append({"recording_id": recording, "archivo": f"audio_muestra/{archivo}",
                             "inicio_s": 0.0, "duracion_s": len(mezcla) / 16000,
                             "metodo": "(canal1 + canal2) / 2; PCM16"})

    guardar(pd.DataFrame(grabaciones), salida / "grabaciones.csv")
    guardar(pd.DataFrame(intervalos), salida / "intervalos.parquet")
    guardar(pd.DataFrame(hablantes), salida / "hablantes.csv")
    guardar(pd.DataFrame(extractos, columns=[
        "recording_id", "archivo", "inicio_s", "duracion_s", "metodo"
    ]), salida / "extractos.csv")
    (salida / "procedencia.json").write_text(json.dumps({
        "origen": "figshare:22647313:v2", "licencia_declarada": cfg["licencia_declarada"],
        "originales": {nombre: lock["archivos"][f"uba_games/figshare-v2/{nombre}"] for nombre in sorted(rutas)},
        "auxiliares": auxiliares, "grabaciones_con_anomalias": anomalías,
        "tolerancia_terminal_figshare_s": TOLERANCIA_FIN_FIGSHARE_S,
        "grabaciones_aceptadas_por_precision": por_precision,
        "max_exceso_terminal_observado_s": max(
            (f["exceso_terminal_max_s"] for f in grabaciones), default=0.0
        ),
        "criterio_extractos": "Primera tarea de cada sesión, primeros 30 segundos, solo pares válidos",
        "politica_segmentos": "Conservar # y etiquetas originales; no generar RTTM sin decidir política de puntuación",
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"sesiones": len(primeras), "grabaciones": len(grabaciones),
            "anotaciones": len(intervalos), "extractos": len(extractos),
            "grabaciones_con_anomalias": len(anomalías),
            "grabaciones_aceptadas_por_precision": len(por_precision)}


def armar_normalizado() -> dict:
    """Regenera las fuentes seleccionadas y publica el contrato común."""
    import os
    import sys

    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from normalizar_muestra import materializar

    # Todos los originales utilizados deben coincidir con el lock.
    lock = json.loads(
        (HITO / "fuentes.lock.json").read_text(encoding="utf-8")
    )
    prefijos = (
        "common_voice/",
        "callhome/",
        "uba_games/figshare-v2/",
        "slr61/",
        "cordeba/",
    )
    elegidos = {p: {} for p in prefijos}

    for nombre, ficha in lock["archivos"].items():
        for prefijo in prefijos:
            if nombre.startswith(prefijo):
                ruta = CACHE / nombre
                if (
                    not ruta.is_file()
                    or ruta.stat().st_size != ficha["bytes"]
                    or sha256(ruta) != ficha["sha256"]
                ):
                    raise ValueError(
                        "Original no coincide con fuentes.lock.json: "
                        f"{nombre}"
                    )
                elegidos[prefijo][nombre] = ficha

    if not all(elegidos.values()):
        raise ValueError(
            "Faltan originales fijados para una o más fuentes principales"
        )

    # Los inventarios se comparan sin confundir informes auxiliares
    # de verificación con originales publicados.
    extensiones = {
        "common_voice/": (".tar.gz",),
        "callhome/": (".parquet",),
        "uba_games/figshare-v2/": (".rar",),
    }

    for prefijo, sufijos in extensiones.items():
        encontrados = {
            f.relative_to(CACHE).as_posix()
            for f in (CACHE / prefijo).rglob("*")
            if f.is_file() and f.name.endswith(sufijos)
        }
        if encontrados != set(elegidos[prefijo]):
            raise ValueError(
                f"Inventario local diferente del lock: {prefijo}"
            )

    # Reutilizamos los adaptadores existentes.
    armar_slr61()
    armar_cordeba()
    armar_uba_games_figshare()

    print("[normalizado]")
    resultado = materializar(
        OUT,
        CACHE,
        OUT / "normalizado",
    )

    # Ampliamos el manifiesto conservando los resultados históricos.
    ruta = OUT / "MANIFIESTO.json"
    previo = (
        json.loads(ruta.read_text(encoding="utf-8"))
        if ruta.is_file()
        else {}
    )
    previo["normalizado"] = {
        **resultado,
        "originales": {
            k: elegidos[k] for k in prefijos
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=ruta.parent,
        prefix=".manifiesto-",
        suffix=".tmp",
        delete=False,
    ) as f:
        json.dump(
            previo,
            f,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        f.write("\n")
        temporal = Path(f.name)

    try:
        os.replace(temporal, ruta)
    finally:
        temporal.unlink(missing_ok=True)

    print(
        "Muestra normalizada validada:",
        {
            nombre: datos["filas"]
            for nombre, datos in resultado["tablas"].items()
        },
    )
    return resultado


def main(argv: list[str] | None = None) -> None:
    # El modo por fuente nunca sobrescribe el manifiesto histórico general.
    # El modo completo conserva el comportamiento previo y agrega Figshare.
    argv = [] if argv is None else argv
    acciones = {
        "normalizado": armar_normalizado,
        "uba_games_figshare": armar_uba_games_figshare,
        "slr61": armar_slr61,
        "cordeba": armar_cordeba,
        "humyn": armar_humyn,
    }
    if len(argv) == 1 and argv[0] in acciones:
        print("Resultado:", json.dumps({argv[0]: acciones[argv[0]]()}, ensure_ascii=False))
        return
    if argv:
        raise SystemExit("Uso: armar_muestra.py [normalizado|uba_games_figshare|slr61|cordeba|humyn]")

    indice = json.loads((CACHE / "audio" / "indice.json").read_text())
    plan = json.loads((CACHE / "audio" / "extractos" / "plan.json").read_text())
    resumen = {"ami": armar_ami(indice["ami"], plan), "icsi": armar_icsi(indice["icsi"], plan),
               "voxconverse": armar_voxconverse(indice["voxconverse"]),
               "slr61": armar_slr61(), "humyn": armar_humyn(), "cordeba": armar_cordeba(),
               "uba_games_figshare": armar_uba_games_figshare()}
    crudos = {str(f.relative_to(CACHE)): {"bytes": f.stat().st_size, "sha256": sha256(f)}
              for f in sorted(CACHE.rglob("*")) if f.is_file() and f.suffix in {".zip", ".txt", ".json", ".wav", ".parquet", ".csv", ".tsv", ".mp3", ".wma", ".rar"}}
    (OUT / "MANIFIESTO.json").write_text(json.dumps({
        "generado": date.today().isoformat(), "semilla": SEMILLA, "por_fuente": resumen, "archivos_crudos": crudos,
    }, ensure_ascii=False, indent=1))
    print("listo ->", OUT.relative_to(HITO.parent))


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
