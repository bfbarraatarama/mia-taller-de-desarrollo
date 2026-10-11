#!/usr/bin/env python3
"""Arma la muestra del Hito 2 (hito-2/muestra/) a partir de las fuentes crudas.

Alcance: reuniones en inglés, para transcribir y separar hablantes.

Uso (desde la raíz del repo, después de `descargar_fuentes.py`):
    .venv/bin/python -I hito-2/scripts/armar_muestra.py

Es determinístico: misma entrada, misma muestra. Lee los archivos comprimidos
en memoria, sin extraerlos al disco. No usa la red.

Qué entra y qué queda afuera, por fuente:

  ami/          Las 171 reuniones: quién habla, cuándo y qué dice (turnos con
                hablante, tiempos y texto), los datos de los participantes y
                un índice del audio de cada reunión. De audio, 16 extractos de
                30 s. Además, la minuta de referencia (resumen, acciones,
                decisiones y problemas) de las 142 reuniones que la tienen.
                Afuera: el audio completo, el video y las demás capas de
                anotación (gestos, temas, actos de diálogo, enlaces de
                evidencia de la minuta, etc.).
  icsi/         Ídem, 75 reuniones y 8 extractos.
  voxconverse/  Quién habla cuándo en las 448 sesiones (RTTM). No tiene
                transcripción. Afuera: el audio.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import soundfile as sf
from lxml import etree

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
        self.total = self.sin_tiempo = 0
        for i, e in enumerate(raiz):
            self.pos[e.get(NITE + "id")] = i
            palabra, puntuacion = es_palabra(e)
            self.items.append((palabra, puntuacion, (e.text or "").strip()))
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


def extractos(corpus: str, plan: list[dict]) -> pd.DataFrame:
    """Pasa los extractos de WAV a FLAC (sin pérdida) y devuelve su tabla."""
    destino = OUT / corpus / "extractos"
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    filas = []
    for p in (p for p in plan if p["corpus"] == corpus):
        datos, hz = sf.read(CACHE / "audio" / "extractos" / f"{p['reunion']}.wav", dtype="int16")
        archivo = f"{p['reunion']}.flac"
        sf.write(destino / archivo, datos, hz, format="FLAC", subtype="PCM_16")
        filas.append({"reunion": p["reunion"], "archivo": f"extractos/{archivo}",
                      "inicio_s": p["inicio_s"], "duracion_s": p["duracion_s"]})
    print(f"  {corpus}/extractos/  {len(filas)} extractos FLAC  "
          f"{sum(f.stat().st_size for f in destino.iterdir()) / 1e6:.2f} MB")
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
    reuniones["tiene_minuta"] = reuniones["reunion"].isin(minutas["reunion"])

    guardar(reuniones, OUT / "ami" / "reuniones.csv")
    guardar(participantes, OUT / "ami" / "participantes.csv")
    guardar(turnos, OUT / "ami" / "turnos.parquet")
    guardar(minutas, OUT / "ami" / "minutas.parquet")
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
               "voxconverse": armar_voxconverse(indice["voxconverse"])}
    crudos = {str(f.relative_to(CACHE)): {"bytes": f.stat().st_size, "sha256": sha256(f)}
              for f in sorted(CACHE.rglob("*")) if f.is_file() and f.suffix in {".zip", ".txt", ".json", ".wav"}}
    (OUT / "MANIFIESTO.json").write_text(json.dumps({
        "generado": date.today().isoformat(), "por_fuente": resumen, "archivos_crudos": crudos,
    }, ensure_ascii=False, indent=1))
    print("listo ->", OUT.relative_to(HITO.parent))


if __name__ == "__main__":
    main()
