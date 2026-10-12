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
import tempfile
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
import soundfile as sf
from lxml import etree

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


def main() -> None:
    indice = json.loads((CACHE / "audio" / "indice.json").read_text())
    plan = json.loads((CACHE / "audio" / "extractos" / "plan.json").read_text())
    resumen = {"ami": armar_ami(indice["ami"], plan), "icsi": armar_icsi(indice["icsi"], plan),
               "voxconverse": armar_voxconverse(indice["voxconverse"]),
               "slr61": armar_slr61(), "humyn": armar_humyn(), "cordeba": armar_cordeba()}
    crudos = {str(f.relative_to(CACHE)): {"bytes": f.stat().st_size, "sha256": sha256(f)}
              for f in sorted(CACHE.rglob("*")) if f.is_file() and f.suffix in {".zip", ".txt", ".json", ".wav", ".parquet", ".csv", ".tsv", ".mp3", ".wma"}}
    (OUT / "MANIFIESTO.json").write_text(json.dumps({
        "generado": date.today().isoformat(), "semilla": SEMILLA, "por_fuente": resumen, "archivos_crudos": crudos,
    }, ensure_ascii=False, indent=1))
    print("listo ->", OUT.relative_to(HITO.parent))


if __name__ == "__main__":
    main()
