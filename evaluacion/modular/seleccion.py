"""Selección determinista de la muestra (requisito «Selección determinista», decisiones D2, D3, D5 y D8).

La selección depende solo de la semilla y del contenido de los originales: cada inventario se ordena antes
de sortear, así que el orden de lectura no cambia el resultado.
"""

from __future__ import annotations

import csv
import io
import random
import statistics
import tarfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from src.rar7z import listar

RAIZ = Path(__file__).resolve().parents[2]
AMI = RAIZ / "hito-2" / "muestra" / "ami"

CV_ARCHIVO = "common_voice/common-voice-scripted-speech-26-0-riopla-0a258d97.tar.gz"
CV_TEST = "es-Rioplatense/test.tsv"
CV_GENEROS = ("female_feminine", "male_masculine")
FIGSHARE_FRASES = "uba_games/figshare-v2/phrases.rar"

# README de wavs.rar (JK, 2021-08-29): S21 a S25 con transcripción completa; S26 a S30 de «annotations_incompleto»;
# la S28 no está. S26 además se usó para desarrollar las Etapas 2 y 4 (D3).
SESIONES_COMPLETAS = ("S21", "S22", "S23", "S24", "S25")
MOTIVOS_EXCLUSION = {
    "S26": "material de desarrollo de la diarización y la asociación (D3); además, transcripción incompleta",
    "S27": "transcripción incompleta según el README de origen (D5)",
    "S28": "no está en la distribución de Figshare v2",
    "S29": "transcripción incompleta según el README de origen (D5)",
    "S30": "transcripción incompleta según el README de origen (D5)",
}


class SeleccionImposible(Exception):
    """Los originales no alcanzan para cumplir los criterios de selección."""


@dataclass(frozen=True, order=True)
class Clip:
    fuente: str      # "openslr" o "common_voice"
    id: str
    hablante: str
    genero: str
    texto: str
    ruta: str        # entrada dentro del archivo original


@dataclass(frozen=True, order=True)
class Reunion:
    id: str
    serie: str
    duracion_s: float
    acciones: int


# ---------- inventarios ----------

def inventario_openslr(cache: Path) -> list[Clip]:
    """Clips de OpenSLR 61 según los índices oficiales; el audio está en es_ar_{genero}.zip como {id}.wav."""
    clips = []
    for genero in ("female", "male"):
        with open(Path(cache) / "slr61" / f"line_index_{genero}.tsv", encoding="utf-8") as f:
            for linea in f:
                if linea.strip():
                    ident, texto = linea.rstrip("\n").split("\t", 1)
                    clips.append(Clip("openslr", ident, ident.rsplit("_", 1)[0], genero, texto.strip(),
                                      f"{ident}.wav"))
    return sorted(clips)


def inventario_common_voice(cache: Path) -> list[Clip]:
    """Clips del split `test` oficial de Common Voice 26 rioplatense, leídos del .tar.gz sin extraerlo."""
    with tarfile.open(Path(cache) / CV_ARCHIVO, "r:gz") as tar:
        datos = tar.extractfile(tar.getmember(CV_TEST)).read().decode("utf-8")
    filas = csv.DictReader(io.StringIO(datos), delimiter="\t", quoting=csv.QUOTE_NONE)
    return sorted(Clip("common_voice", f["path"], f["client_id"], f["gender"], f["sentence"].strip(),
                       f"es-Rioplatense/clips/{f['path']}") for f in filas)


def sesiones_figshare(cache: Path) -> list[str]:
    """Sesiones presentes en phrases.rar (sin extraer)."""
    nombres = listar(Path(cache) / FIGSHARE_FRASES)
    return sorted({n.split("/")[1] for n in nombres if n.count("/") >= 2 and n.startswith("phrases/S")})


def inventario_ami(carpeta: Path = AMI) -> list[Reunion]:
    """Reuniones de AMI con minuta de referencia, con su serie, duración y cantidad de ítems de acción."""
    import pandas as pd

    reuniones = pd.read_csv(Path(carpeta) / "reuniones.csv")
    minutas = pd.read_parquet(Path(carpeta) / "minutas.parquet")
    acciones = minutas[minutas.tipo == "accion"].groupby("reunion").size()
    con_minuta = reuniones[reuniones.tiene_minuta.astype(bool)]
    return sorted(Reunion(r.reunion, r.serie, float(r.duracion_s), int(acciones.get(r.reunion, 0)))
                  for r in con_minuta.itertuples())


# ---------- selección ----------

def _por_hablante(clips: list[Clip]) -> dict[str, list[Clip]]:
    grupos = defaultdict(list)
    for c in sorted(clips):
        grupos[c.hablante].append(c)
    return grupos


def seleccionar_clips(openslr: list[Clip], common_voice: list[Clip], semilla: int) -> list[Clip]:
    """3 de OpenSLR (una mujer, un hombre y uno más) y 2 de Common Voice (una mujer y un hombre), 5 personas (D2)."""
    rng = random.Random(semilla)
    slr = _por_hablante(openslr)
    mujeres = sorted(h for h, cs in slr.items() if cs[0].genero == "female")
    hombres = sorted(h for h, cs in slr.items() if cs[0].genero == "male")
    if not mujeres or not hombres or len(slr) < 3:
        raise SeleccionImposible("OpenSLR 61 necesita al menos una mujer, un hombre y tres hablantes")
    elegidos = [rng.choice(mujeres), rng.choice(hombres)]
    elegidos.append(rng.choice(sorted(set(slr) - set(elegidos))))
    clips = [rng.choice(slr[h]) for h in elegidos]

    cv = _por_hablante([c for c in common_voice if c.genero in CV_GENEROS])
    for genero in CV_GENEROS:
        candidatos = sorted(h for h, cs in cv.items() if cs[0].genero == genero)
        if not candidatos:
            raise SeleccionImposible(f"Common Voice (test) no tiene clips con género {genero}")
        clips.append(rng.choice(cv[rng.choice(candidatos)]))
    return clips


def seleccionar_sesiones(sesiones: list[str], semilla: int) -> tuple[list[str], dict[str, str]]:
    """3 sesiones completas de Figshare, sin S26 a S30 (D3, D5); devuelve las elegidas y el motivo de cada exclusión."""
    candidatas = sorted(set(sesiones) & set(SESIONES_COMPLETAS))
    if len(candidatas) < 3:
        raise SeleccionImposible(f"hay {len(candidatas)} sesiones con transcripción completa y se necesitan 3")
    elegidas = sorted(random.Random(semilla).sample(candidatas, 3))
    return elegidas, dict(MOTIVOS_EXCLUSION)


def seleccionar_reuniones(reuniones: list[Reunion], semilla: int) -> list[Reunion]:
    """3 reuniones de series distintas, con al menos una acción y duración entre los percentiles 25 y 75 (D8)."""
    con_accion = sorted(r for r in reuniones if r.acciones >= 1)
    if len(con_accion) < 3:
        raise SeleccionImposible("hay menos de 3 reuniones de AMI con ítems de acción")
    p25, _, p75 = statistics.quantiles([r.duracion_s for r in con_accion], n=4, method="inclusive")
    candidatas = [r for r in con_accion if p25 <= r.duracion_s <= p75]
    random.Random(semilla).shuffle(candidatas)
    elegidas, series = [], set()
    for r in candidatas:
        if r.serie not in series:
            elegidas.append(r)
            series.add(r.serie)
        if len(elegidas) == 3:
            return sorted(elegidas)
    raise SeleccionImposible(f"las reuniones candidatas cubren {len(series)} series y se necesitan 3")
