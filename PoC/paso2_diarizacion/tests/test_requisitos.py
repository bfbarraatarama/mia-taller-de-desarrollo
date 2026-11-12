"""Comprobación del entorno de los niveles 2 y 3: informa qué falta en cada máquina (`pytest -m "slow or gpu" -rs`)."""

import pytest


@pytest.mark.slow
def test_entorno_nivel2_cpu(token_hf, audios_cpu, ffmpeg):
    assert audios_cpu and ffmpeg


@pytest.mark.slow
def test_herramienta_7zip(siete_zip):
    assert siete_zip


@pytest.mark.gpu
def test_entorno_nivel3_gpu(token_hf, dataset_figshare, ffmpeg, cuda):
    assert dataset_figshare.is_dir() and cuda
