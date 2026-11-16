"""Traducción sintética de AMI y entrada de la Etapa 5 (requisito «Traducción sintética de AMI», D6, D7 y D14).

Cada reunión elegida queda como carpeta con:
- `transcription.json`: turnos traducidos, con la letra del participante como etiqueta, su rol traducido como
  nombre (o `null` si la reunión no tiene roles), `overlap` con la regla D5 de la asociación y `ambiguous: false`;
- `referencia_minuta.json`: ítems de la minuta de referencia traducidos, para la planilla de minutas;
- `traduccion.json`: cada texto original con su traducción, marcado como sintético con el modelo y la revisión.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

from src.asociacion.asociacion import OVERLAP_MIN_MS, Turnos, ms
from src.tiempos import cuantizar_intervalo

RAIZ = Path(__file__).resolve().parents[2]
AMI = RAIZ / "hito-2" / "muestra" / "ami"
AMI_ZIP = RAIZ / "hito-2" / ".cache" / "ami" / "ami_public_manual_1.6.2.zip"

MODELO = "Helsinki-NLP/opus-mt-en-es"
REVISION = "5bc4493d463cf000c1f0b50f8d56886a392ed4ab"  # 16/08/2023, Apache 2.0
ARCHIVOS_MODELO = ["config.json", "generation_config.json", "pytorch_model.bin", "source.spm", "target.spm",
                   "tokenizer_config.json", "vocab.json"]
MAX_PALABRAS = 200  # por fragmento: MarianMT corta a 512 tokens
LOTE = 16

# Roles de las reuniones de escenario de AMI, en el mismo registro que usa la traducción de las minutas.
ROLES = {"PM": "Gerente de proyecto", "ME": "Experto en marketing", "UI": "Diseñador de interfaz",
         "ID": "Diseñador industrial"}


def modelo_en_cache() -> bool:
    from huggingface_hub import try_to_load_from_cache

    return all(isinstance(try_to_load_from_cache(MODELO, a, revision=REVISION), str) for a in ARCHIVOS_MODELO)


class Traductor:
    """MarianMT en una revisión fija, sin muestreo (búsqueda determinista)."""

    modelo, revision = MODELO, REVISION

    def __init__(self, dispositivo: str = "cpu"):
        import torch
        from transformers import MarianMTModel, MarianTokenizer

        self._torch = torch
        self.tokenizer = MarianTokenizer.from_pretrained(MODELO, revision=REVISION)
        self.red = MarianMTModel.from_pretrained(MODELO, revision=REVISION).to(dispositivo).eval()
        self.dispositivo = dispositivo
        self.parametros = {"do_sample": False, "num_beams": self.red.generation_config.num_beams,
                           "max_length": self.red.generation_config.max_length, "dispositivo": dispositivo,
                           "lote": LOTE}

    def traducir(self, textos: list[str]) -> list[str]:
        salida = []
        for i in range(0, len(textos), LOTE):
            lote = self.tokenizer(textos[i:i + LOTE], return_tensors="pt", padding=True, truncation=True)
            with self._torch.no_grad():
                generado = self.red.generate(**lote.to(self.dispositivo), do_sample=False,
                                             num_beams=self.parametros["num_beams"])
            salida += self.tokenizer.batch_decode(generado, skip_special_tokens=True)
        return [t.strip() for t in salida]


def oraciones(texto: str, max_palabras: int = MAX_PALABRAS) -> list[str]:
    """Oraciones del texto; las que superan `max_palabras` se parten en fragmentos sin perder palabras."""
    partes = []
    for oracion in re.split(r"(?<=[.!?])\s+", texto.strip()):
        palabras = oracion.split()
        partes += [" ".join(palabras[i:i + max_palabras]) for i in range(0, len(palabras), max_palabras)]
    return [p for p in partes if p]


def traducir_textos(textos: list[str], traductor) -> list[str]:
    """Traduce por oraciones y vuelve a unir; cada oración distinta se traduce una sola vez."""
    por_texto = [oraciones(t) for t in textos]
    unicas = list(dict.fromkeys(o for partes in por_texto for o in partes))
    traducidas = dict(zip(unicas, traductor.traducir(unicas))) if unicas else {}
    return [" ".join(traducidas[o] for o in partes) for partes in por_texto]


def roles_ami(reunion: str, ami_zip: Path = AMI_ZIP) -> dict[str, str]:
    """{letra del participante: rol} desde corpusResources/meetings.xml; vacío si la reunión no tiene roles."""
    xml = zipfile.ZipFile(ami_zip).read("corpusResources/meetings.xml").decode("latin1")
    inicio = xml.index(f'observation="{reunion}"')
    bloque = xml[inicio:xml.index("</meeting>", inicio)]
    roles = {}
    for speaker in re.findall(r"<speaker\b[^>]*>", bloque):
        agente, rol = re.search(r'nxt_agent="([^"]+)"', speaker), re.search(r'role="([^"]+)"', speaker)
        if agente and rol:
            roles[agente.group(1)] = rol.group(1)
    return roles


def _datos_ami(reunion: str, carpeta: Path) -> tuple[list[tuple], list[tuple]]:
    import pandas as pd

    t = pd.read_parquet(carpeta / "turnos.parquet")
    t = t[t.reunion == reunion].sort_values(["inicio", "fin"], kind="stable")
    m = pd.read_parquet(carpeta / "minutas.parquet")
    m = m[m.reunion == reunion].sort_values(["tipo", "orden"], kind="stable")
    return ([(r.agente, float(r.inicio), float(r.fin), r.texto) for r in t.itertuples()],
            [(r.tipo, r.item_id, r.texto) for r in m.itertuples()])


def _escribir(ruta: Path, datos: dict) -> str:
    contenido = json.dumps(datos, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    ruta.write_bytes(contenido)
    return hashlib.sha256(contenido).hexdigest()


def preparar_reunion_ami(reunion: str, carpeta: Path, traductor, *, turnos: list[tuple] | None = None,
                         items: list[tuple] | None = None, roles: dict[str, str] | None = None) -> dict:
    """Traduce una reunión de AMI y escribe su entrada para la Etapa 5; devuelve el registro para el manifiesto."""
    if turnos is None or items is None:
        turnos, items = _datos_ami(reunion, AMI)
    roles = roles_ami(reunion) if roles is None else roles
    validos = [(a, i, f, x.strip()) for a, i, f, x in turnos if f > i and x and x.strip()]
    textos = traducir_textos([x for *_, x in validos] + [x for _, _, x in items], traductor)
    turnos_es, items_es = textos[:len(validos)], textos[len(validos):]

    mapa = Turnos([{"start": i, "end": f, "speaker": a} for a, i, f, _ in validos])
    segmentos, registro_turnos = [], []
    for (agente, ini, fin, original), texto in zip(validos, turnos_es):
        registro_turnos.append({"agente": agente, "inicio": ini, "fin": fin, "texto_original": original,
                                "texto": texto})
        if not texto:
            continue
        start, end = cuantizar_intervalo(ini, fin)
        segmentos.append({"start": start, "end": end, "speaker": agente, "name": ROLES.get(roles.get(agente)),
                          "text": texto, "overlap": mapa.superpuesto(ms(ini), ms(fin)) >= OVERLAP_MIN_MS,
                          "ambiguous": False})
    segmentos.sort(key=lambda s: s["start"])

    marca = {"sintetico": True, "modelo": traductor.modelo, "revision": traductor.revision,
             "parametros": traductor.parametros}
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    hashes = {
        "transcription.json": _escribir(carpeta / "transcription.json", {"segments": segmentos}),
        "traduccion.json": _escribir(carpeta / "traduccion.json",
                                     {**marca, "reunion": reunion, "roles": roles, "turnos": registro_turnos}),
        "referencia_minuta.json": _escribir(carpeta / "referencia_minuta.json", {
            **marca, "reunion": reunion,
            "items": [{"tipo": t, "item_id": i, "texto": x, "texto_original": o}
                      for (t, i, o), x in zip(items, items_es)]}),
    }
    return {"reunion": reunion, **marca, "turnos": len(segmentos), "descartados": len(turnos) - len(segmentos),
            "items": len(items), "roles": roles, "archivos": hashes}
