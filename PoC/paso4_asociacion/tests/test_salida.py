"""Tareas 2.6 a 2.8: escritura segura, metadatos, errores, CLI, rutas y lectura por la Etapa 5."""

from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path

import pytest

from asociar import main, procesar
from conftest import MODULO, leer, sha256
from errores import AsociacionError

ENTRADAS = ("audio.wav", "diarization.json", "asr.json")
SALIDAS = ("transcription.json", "transcription.meta.json")


def romper_diarizacion(carpeta: Path) -> None:
    datos = leer(carpeta / "diarization.json")
    datos["segments"][0]["end"] = 99.0
    (carpeta / "diarization.json").write_text(json.dumps(datos), encoding="utf-8")


# ---------- 2.6 escritura ----------


def test_metadatos_coherentes_con_el_resultado(reunion):
    procesar(reunion)
    meta = leer(reunion / "transcription.meta.json")
    assert meta["sha256"]["transcription.json"] == sha256(reunion / "transcription.json")
    for nombre in ENTRADAS:
        assert meta["sha256"][nombre] == sha256(reunion / nombre)
    assert meta["etiquetado"] is False
    assert meta["conteos"]["intervenciones"] == 3


def test_falla_con_un_resultado_anterior(reunion):
    procesar(reunion)
    antes = {n: sha256(reunion / n) for n in SALIDAS}
    romper_diarizacion(reunion)
    with pytest.raises(AsociacionError):
        procesar(reunion)
    assert {n: sha256(reunion / n) for n in SALIDAS} == antes
    assert not list(reunion.glob("*.tmp"))


def test_entradas_intactas(reunion):
    antes = {n: sha256(reunion / n) for n in ENTRADAS}
    procesar(reunion)
    assert {n: sha256(reunion / n) for n in ENTRADAS} == antes
    romper_diarizacion(reunion)
    antes = {n: sha256(reunion / n) for n in ENTRADAS}
    with pytest.raises(AsociacionError):
        procesar(reunion)
    assert {n: sha256(reunion / n) for n in ENTRADAS} == antes


def test_error_registrado(reunion):
    romper_diarizacion(reunion)
    with pytest.raises(AsociacionError):
        procesar(reunion)
    error = leer(reunion / "transcription.error.json")
    assert error["paso"] == "diarizacion"
    assert error["archivo"].endswith("diarization.json")
    assert any("supera la duración" in v for v in error["violaciones"])
    assert error["resultado_anterior"] is False


def test_exito_posterior(reunion):
    original = (reunion / "diarization.json").read_bytes()
    romper_diarizacion(reunion)
    with pytest.raises(AsociacionError):
        procesar(reunion)
    (reunion / "diarization.json").write_bytes(original)
    procesar(reunion)
    assert not (reunion / "transcription.error.json").exists()


# ---------- 2.7 CLI y rutas ----------


def test_fallo_con_resultado_anterior_presente(reunion, capsys):
    assert main([str(reunion)]) == 0
    romper_diarizacion(reunion)
    assert main([str(reunion)]) == 1
    assert "diarization.json" in capsys.readouterr().err


def test_carpeta_de_la_reunion(reunion):
    assert main([str(reunion)]) == 0
    for nombre in SALIDAS:
        assert (reunion / nombre).is_file()


def test_rutas_explicitas(reunion, tmp_path):
    otra = tmp_path / "otra"
    otra.mkdir()
    diar = otra / "figshare_v2_S26_objects_01.json"
    asr = otra / "asr.json"
    (reunion / "diarization.json").rename(diar)
    (reunion / "asr.json").rename(asr)
    salida = tmp_path / "salida"
    antes = sorted(p.name for p in otra.iterdir())
    assert main(["--audio", str(reunion / "audio.wav"), "--diarizacion", str(diar), "--asr", str(asr),
                 "--salida", str(salida)]) == 0
    assert (salida / "transcription.json").is_file()
    assert sorted(p.name for p in otra.iterdir()) == antes
    assert sorted(p.name for p in reunion.iterdir()) == ["audio.wav"]


def test_rutas_incompletas(tmp_path, capsys):
    assert main(["--audio", str(tmp_path / "a.wav")]) == 1
    assert "diarizacion" in capsys.readouterr().err


def test_sin_interfaz(reunion):
    assert main([str(reunion)]) == 0
    assert not (reunion / "speakers.json").exists()
    assert all(s["name"] is None for s in leer(reunion / "transcription.json")["segments"])


# ---------- 2.8 lectura por la Etapa 5 ----------


def _etapa5() -> Path:
    return Path(os.environ.get("ETAPA5_SRC", MODULO.parents[1] / "src")) / "minutas"


def _lector_etapa5():
    """Carga solo entrada.py y contratos.py de la Etapa 5, sin su __init__ (que importa Ollama y boto3)."""
    pytest.importorskip("pydantic", reason="falta pydantic (entorno de la Etapa 5)")
    if not (_etapa5() / "entrada.py").is_file():
        pytest.skip("falta la Etapa 5 (PR #6); se puede indicar con ETAPA5_SRC")
    paquete = types.ModuleType("minutas")
    paquete.__path__ = [str(_etapa5())]
    sys.modules["minutas"] = paquete
    try:
        return importlib.import_module("minutas.entrada")
    finally:
        for nombre in [n for n in sys.modules if n == "minutas" or n.startswith("minutas.")]:
            del sys.modules[nombre]


def test_lectura_por_la_etapa_5(reunion):
    entrada = _lector_etapa5()
    procesar(reunion)
    intervenciones, _ = entrada.leer_transcripcion(reunion / "transcription.json")
    assert [i.hablante for i in intervenciones] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"]
