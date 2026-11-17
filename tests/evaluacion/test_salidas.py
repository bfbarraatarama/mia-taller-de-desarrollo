"""Salidas de los módulos versionadas para recalcular sin GPU (criterio de cierre del issue #13)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluacion.modular.salidas import ARCHIVOS, publicar_salidas
from tests.evaluacion.test_contratos import armar
from tests.evaluacion.test_evaluar_sin_gpu import config_con, evaluar_sin_gpu


def test_publicar_salidas(tmp_path):
    _, _, inferencia = armar(tmp_path)
    (inferencia / "clip-c1" / "audio.wav").write_bytes(b"audio")          # no se publica
    (inferencia / "clip-c1" / "inferencia.log").write_text("ruta /home/x")  # tampoco
    (inferencia / "clip-c1" / "inferencia.json").write_text("{}")
    destino = tmp_path / "salidas"
    assert publicar_salidas(inferencia, destino) == 13  # 9 JSON, 2 minutes.md (Figshare, AMI) y 2 inferencia.json más
    publicados = sorted(p.relative_to(destino).as_posix() for p in destino.rglob("*") if p.is_file())
    assert "clip-c1/asr.json" in publicados and "clip-c1/inferencia.json" in publicados
    assert all(Path(p).name in ARCHIVOS for p in publicados)
    (inferencia / "clip-c1" / "asr.json").unlink()
    publicar_salidas(inferencia, destino)  # se reemplaza entera: no quedan salidas viejas
    assert not (destino / "clip-c1" / "asr.json").exists()


def test_evaluar_desde_salidas_versionadas(tmp_path):
    manifiesto, datos, inferencia = armar(tmp_path)
    salidas = tmp_path / "salidas"
    publicar_salidas(inferencia, salidas)
    con_inferencia = config_con(tmp_path, salida=datos, manifiesto=manifiesto, inferencia=inferencia,
                                resultados=tmp_path / "r1", salidas=tmp_path / "publicadas")
    assert evaluar_sin_gpu(con_inferencia) == (0, [])
    assert (tmp_path / "publicadas" / "clip-c1" / "asr.json").is_file()  # evaluar publica las salidas
    (tmp_path / "config.toml").rename(tmp_path / "config1.toml")
    sin_inferencia = config_con(tmp_path, salida=datos, manifiesto=manifiesto, inferencia=tmp_path / "no-existe",
                                resultados=tmp_path / "r2", salidas=salidas)
    assert evaluar_sin_gpu(sin_inferencia) == (0, [])
    uno = json.loads((tmp_path / "r1/contratos.json").read_text(encoding="utf-8"))
    dos = json.loads((tmp_path / "r2/contratos.json").read_text(encoding="utf-8"))
    assert uno == dos and dos["cumple"] is True
