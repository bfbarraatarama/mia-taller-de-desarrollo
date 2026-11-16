"""Tarea 6.5: evaluación sin inferencia (requisito «Evaluación sin inferencia», escenario «Recalcular métricas»).

`evaluar` corre en un proceso aparte con la GPU oculta (CUDA_VISIBLE_DEVICES vacío), como en una máquina sin GPU.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from evaluacion.modular.config import cargar_config
from tests.evaluacion.test_contratos import armar

RAIZ = Path(__file__).resolve().parents[2]
PESADOS = ("torch", "whisper", "pyannote.audio", "transformers", "ollama", "boto3")
REPORTES = ("contratos.json", "metricas_stt.json", "metricas_diarizacion.json", "metricas_asociacion.json")


def evaluar_sin_gpu(config: Path) -> tuple[int, list[str]]:
    codigo = ("import json, sys\n"
              "from evaluacion.modular.__main__ import main\n"
              f"rc = main(['evaluar', '--config', {str(config)!r}])\n"
              f"print(json.dumps([rc, [m for m in {PESADOS!r} if m in sys.modules]]))\n")
    entorno = {**os.environ, "CUDA_VISIBLE_DEVICES": ""}
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=entorno, capture_output=True, text=True,
                       check=True)
    rc, cargados = json.loads(r.stdout.strip().splitlines()[-1])
    return rc, cargados


def config_con(tmp_path: Path, **rutas) -> Path:
    texto = (RAIZ / "evaluacion/modular/config.toml").read_text(encoding="utf-8")
    for clave, valor in rutas.items():
        actual = {"salida": "evaluacion/modular/datos", "manifiesto": "evaluacion/modular/muestra.manifest.json",
                  "inferencia": "evaluacion/modular/inferencia", "resultados": "evaluacion/modular/resultados"}[clave]
        texto = texto.replace(f'{clave} = "{actual}"', f'{clave} = "{valor}"')
    ruta = tmp_path / "config.toml"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def test_recalcular_metricas_sin_cargar_modelos(tmp_path):
    manifiesto, datos, inferencia = armar(tmp_path)
    config = config_con(tmp_path, salida=datos, manifiesto=manifiesto, inferencia=inferencia,
                        resultados=tmp_path / "resultados")
    rc, cargados = evaluar_sin_gpu(config)
    assert rc == 0
    assert cargados == []
    assert all((tmp_path / "resultados" / r).is_file() for r in REPORTES)


def test_recalcular_metricas_reales(tmp_path):
    """Con las salidas de la corrida de referencia, reproduce byte a byte los reportes versionados."""
    config = cargar_config()
    if not (config.inferencia.is_dir() and config.salida.is_dir()):
        pytest.skip("faltan la muestra o las salidas de la corrida de referencia (preparar e inferir)")
    rc, cargados = evaluar_sin_gpu(config_con(tmp_path, resultados=tmp_path / "resultados"))
    assert (rc, cargados) == (0, [])
    for reporte in REPORTES:
        assert (tmp_path / "resultados" / reporte).read_bytes() == (config.resultados / reporte).read_bytes(), reporte
