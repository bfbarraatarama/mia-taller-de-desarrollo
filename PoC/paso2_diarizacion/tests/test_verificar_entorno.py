"""Coherencia de requirements.txt y constraints.txt, y lógica del verificador de entorno."""

import re

import pytest

from conftest import MODULO
from verificar_entorno import DIRECTAS, cumple, leer_restricciones, normalizar_nombre

VERSIONES_VERIFICADAS = {"torch": "==2.8.0", "torchaudio": "==2.8.0", "torchcodec": "==0.7.0",
                         "pyannote-audio": "==4.0.7"}


def test_constraints_fija_las_versiones_verificadas():
    r = leer_restricciones()
    for nombre, espec in VERSIONES_VERIFICADAS.items():
        assert r[nombre] == espec
    for nombre in DIRECTAS:
        assert normalizar_nombre(nombre) in r, f"{nombre} no está en constraints.txt"


def test_constraints_no_tiene_etiquetas_locales_ni_duplicados():
    lineas = [l.split("#", 1)[0].strip() for l in (MODULO / "constraints.txt").read_text(encoding="utf-8").splitlines()]
    nombres = [normalizar_nombre(l.split("==")[0]) for l in lineas if l]
    assert len(nombres) == len(set(nombres))
    assert not any("+cpu" in l or "+cu" in l for l in lineas)


def test_requirements_coincide_con_constraints_y_no_incluye_pytorch():
    r = leer_restricciones()
    directas = {}
    for linea in (MODULO / "requirements.txt").read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if linea:
            nombre, espec = re.fullmatch(r"([A-Za-z0-9._-]+)\s*(==\S+)", linea).groups()
            directas[normalizar_nombre(nombre)] = espec
    assert "torch" not in directas and "torchaudio" not in directas  # PyTorch se instala aparte (CPU o cu128)
    for nombre, espec in directas.items():
        assert r[nombre] == espec, nombre


@pytest.mark.parametrize("instalada, espec, esperado", [
    ("2.8.0+cpu", "==2.8.0", True), ("2.8.0+cu128", "==2.8.0", True), ("2.15.0", "==2.8.0", False),
    ("0.7.0", "==0.7.0", True), ("0.7.0", "==0.7.*", True), ("0.17.0", "==0.7.*", False),
])
def test_cumple_sigue_pep_440(instalada, espec, esperado):
    assert cumple(instalada, espec) is esperado


def test_linea_no_reconocida(tmp_path):
    ruta = tmp_path / "constraints.txt"
    ruta.write_text("torch>=2.8\n", encoding="utf-8")
    with pytest.raises(ValueError):
        leer_restricciones(ruta)
