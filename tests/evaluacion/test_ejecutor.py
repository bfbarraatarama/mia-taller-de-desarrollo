"""Tarea 1.1: estructura del ejecutor y configuración versionada (issue #13).

Escenarios de `docs/evaluacion/openspec/changes/evaluacion-modular/specs/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluacion.modular.__main__ import construir_parser, main
from evaluacion.modular.config import CONFIG_POR_DEFECTO, cargar_config

RAIZ = Path(__file__).resolve().parents[2]


def test_cli_con_tres_comandos():
    parser = construir_parser()
    comandos = parser._subparsers._group_actions[0].choices
    assert set(comandos) == {"preparar", "inferir", "evaluar"}


def test_cli_ayuda(capsys):
    with pytest.raises(SystemExit) as salida:
        main(["--help"])
    assert salida.value.code == 0
    assert "preparar" in capsys.readouterr().out


def test_configuracion_versionada():
    assert CONFIG_POR_DEFECTO == RAIZ / "evaluacion" / "modular" / "config.toml"
    config = cargar_config()
    assert config.semilla == 20261010
    assert set(config.originales) == {"common_voice", "figshare_frases", "figshare_audio", "openslr_mujeres",
                                      "openslr_hombres", "openslr_indice_mujeres", "openslr_indice_hombres", "ami"}


def test_originales_con_hash_fijado():
    """Cada original de la configuración tiene un hash fijado en el lock o en fuentes.toml del Hito 2."""
    for original in cargar_config().originales.values():
        assert original.sha256 or original.md5, original.clave
        assert original.bytes > 0, original.clave
        assert original.obtener, original.clave


def test_semilla_distinta_por_parametro(tmp_path):
    texto = (RAIZ / "evaluacion" / "modular" / "config.toml").read_text(encoding="utf-8")
    otro = tmp_path / "config.toml"
    otro.write_text(texto.replace("semilla = 20261010", "semilla = 7"), encoding="utf-8")
    assert cargar_config(otro).semilla == 7
