"""Tarea 4.1: traducción sintética de AMI y entrada de la Etapa 5 (requisito «Traducción sintética de AMI», D6, D7, D14)."""

from __future__ import annotations

import json

import pytest

from evaluacion.modular.traduccion import (MODELO, REVISION, ROLES, Traductor, modelo_en_cache, oraciones,
                                           preparar_reunion_ami, traducir_textos)
from src.asociacion.contrato import validar_transcripcion
from src.minutas.entrada import leer_transcripcion


class TraductorFalso:
    """Determinista y sin modelo: antepone «ES:» a cada oración y cuenta las llamadas."""

    modelo, revision, parametros = "falso", "0", {"do_sample": False}

    def __init__(self):
        self.vistas = []

    def traducir(self, textos):
        self.vistas.extend(textos)
        return [f"ES:{t}" for t in textos]


def test_oraciones_largas_se_parten_sin_perder_texto():
    texto = "Uh I guess I start. " + " ".join(["word"] * 450) + ". Okay?"
    partes = oraciones(texto, max_palabras=200)
    assert all(len(p.split()) <= 200 for p in partes)
    assert " ".join(partes).split() == texto.split()


def test_traduccion_por_oraciones_y_sin_repetir():
    falso = TraductorFalso()
    salida = traducir_textos(["Okay. We start.", "Okay."], falso)
    assert salida == ["ES:Okay. ES:We start.", "ES:Okay."]
    assert falso.vistas.count("Okay.") == 1  # una oración repetida se traduce una vez


TURNOS = [  # (agente, inicio, fin, texto)
    ("A", 0.0, 4.0, "We start with the budget."),
    ("B", 3.5, 6.0, "Okay."),           # 0,5 s con A: overlap
    ("A", 6.5, 7.0, "Right."),
    ("C", 6.9, 7.5, "Yes."),            # 0,1 s con A: sin overlap
    ("B", 8.0, 8.0, "Mm."),             # sin duración: se descarta
]
ITEMS = [("accion", "IS1009c.x.a.1", "The industrial designer will work on the prototype."),
         ("resumen", "IS1009c.x.s.1", "The team discussed the budget.")]


def preparar(tmp_path, roles):
    return preparar_reunion_ami("IS1009c", tmp_path / "IS1009c", TraductorFalso(),
                                turnos=TURNOS, items=ITEMS, roles=roles)


def test_marca_de_sintetico(tmp_path):
    registro = preparar(tmp_path, {"A": "PM", "B": "ID", "C": "UI"})
    assert registro["sintetico"] is True
    assert (registro["modelo"], registro["revision"]) == ("falso", "0")
    trad = json.loads((tmp_path / "IS1009c" / "traduccion.json").read_text(encoding="utf-8"))
    assert trad["sintetico"] is True and trad["modelo"] == "falso"
    assert {t["texto_original"] for t in trad["turnos"]} >= {"We start with the budget.", "Okay."}
    ref = json.loads((tmp_path / "IS1009c" / "referencia_minuta.json").read_text(encoding="utf-8"))
    assert ref["sintetico"] is True
    assert ref["items"][0] == {"tipo": "accion", "item_id": "IS1009c.x.a.1",
                               "texto": "ES:The industrial designer will work on the prototype.",
                               "texto_original": "The industrial designer will work on the prototype."}


def test_entrada_de_la_etapa_5_con_roles(tmp_path):
    preparar(tmp_path, {"A": "PM", "B": "ID", "C": "UI"})
    carpeta = tmp_path / "IS1009c"
    datos = json.loads((carpeta / "transcription.json").read_text(encoding="utf-8"))
    segs = datos["segments"]
    assert [s["speaker"] for s in segs] == ["A", "B", "A", "C"]
    assert segs[0]["name"] == ROLES["PM"] and segs[1]["name"] == ROLES["ID"]
    assert [s["overlap"] for s in segs] == [True, True, False, False]
    assert not any(s["ambiguous"] for s in segs)
    assert validar_transcripcion(datos, 7.5, {"A", "B", "C"}) == []
    intervenciones, _ = leer_transcripcion(carpeta / "transcription.json")
    assert len(intervenciones) == 4


def test_reunion_sin_roles_va_sin_nombre(tmp_path):
    preparar(tmp_path, {})
    segs = json.loads((tmp_path / "IS1009c" / "transcription.json").read_text(encoding="utf-8"))["segments"]
    assert all(s["name"] is None for s in segs)


@pytest.mark.skipif(not modelo_en_cache(), reason=f"falta {MODELO}@{REVISION[:7]} en la caché de Hugging Face")
def test_traduccion_repetible():
    textos = ["The industrial designer will come up with a user interface design.", "Okay."]
    primera = traducir_textos(textos, Traductor())
    segunda = traducir_textos(textos, Traductor())
    assert primera == segunda
    assert all(t and t != o for t, o in zip(primera, textos))
