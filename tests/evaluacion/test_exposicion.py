"""Tarea 7.1: informe de exposición previa (requisito «Informe de exposición previa»)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluacion.modular.exposicion import EXPOSICION, ExposicionIncompleta, informe_exposicion

RAIZ = Path(__file__).resolve().parents[2]


def manifiesto() -> dict:
    return json.loads((RAIZ / "evaluacion/modular/muestra.manifest.json").read_text(encoding="utf-8"))


def test_fuente_de_desarrollo_excluida():
    informe = informe_exposicion(manifiesto())
    s26 = informe["excluidos"]["S26"]
    assert "desarrollo" in s26["motivo"] and "diarización" in s26["motivo"] and "asociación" in s26["motivo"]
    assert s26["en_la_muestra"] is False
    assert all(e["sesion"] != "S26" for e in manifiesto()["contenido"]["elementos"] if e["fuente"] == "figshare")


def test_cada_fuente_declara_sus_modelos():
    informe = informe_exposicion(manifiesto())
    assert set(informe["fuentes"]) == {"openslr", "common_voice", "figshare", "ami"}
    assert set(informe["fuentes"]["openslr"]["entrenamiento"]) == {"whisper"}
    assert set(informe["fuentes"]["figshare"]["entrenamiento"]) == {"whisper", "pyannote", "qwen"}
    assert set(informe["fuentes"]["ami"]["entrenamiento"]) == {"qwen"}
    for fuente in informe["fuentes"].values():
        assert fuente["desarrollo"]["estado"] in {"no usada", "usada", "a confirmar"}
        for modelo in fuente["entrenamiento"].values():
            assert modelo["estado"] in {"descartada", "no se puede descartar", "a confirmar"}
            assert modelo["evidencia"]


def test_fuente_sin_declarar(tmp_path):
    incompleto = tmp_path / "exposicion.toml"
    texto = EXPOSICION.read_text(encoding="utf-8")
    incompleto.write_text(texto[:texto.index("[fuentes.ami.")], encoding="utf-8")
    with pytest.raises(ExposicionIncompleta, match="ami"):
        informe_exposicion(manifiesto(), incompleto)


def test_modelo_sin_declarar(tmp_path):
    incompleto = tmp_path / "exposicion.toml"
    texto = EXPOSICION.read_text(encoding="utf-8")
    inicio = texto.index("[fuentes.figshare.entrenamiento.pyannote]")
    fin = texto.index("[", inicio + 1)
    incompleto.write_text(texto[:inicio] + texto[fin:], encoding="utf-8")
    with pytest.raises(ExposicionIncompleta, match="figshare.*pyannote"):
        informe_exposicion(manifiesto(), incompleto)
