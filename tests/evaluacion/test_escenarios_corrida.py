"""Revisión del #24: cada corrida se comprueba sobre su propia carpeta, sin restos de una corrida anterior."""

from __future__ import annotations

import json

import evaluacion.escenarios.__main__ as escenarios
from evaluacion.escenarios.entradas import construir_manifiesto


def config_en(tmp_path, monkeypatch) -> dict:
    monkeypatch.setattr(escenarios, "RAIZ", tmp_path)
    entrada = tmp_path / "entrada.wav"
    entrada.write_bytes(b"audio")
    manifiesto = tmp_path / "entradas.manifest.json"
    manifiesto.write_text(json.dumps(construir_manifiesto({"2.1.4": {"fuentes": [entrada]}}, tmp_path)))
    return {"manifiesto": manifiesto, "corridas": tmp_path / "corridas", "resultados": tmp_path / "resultados",
            "modelos": {"modelo_stt": "medium", "dispositivo": "cuda", "modelo_minutas": "qwen2.5-7b",
                        "secciones": ["resumen"]}}


def test_corrida_fallida_no_hereda_restos_de_la_anterior(tmp_path, monkeypatch):
    c = config_en(tmp_path, monkeypatch)
    vieja = c["corridas"] / "2.1.4"
    vieja.mkdir(parents=True)
    (vieja / "workflow.json").write_text('{"estado": "completado", "error": null}')  # resto de una corrida anterior
    (vieja / "transcription.json").write_text('{"segments": []}')
    assert escenarios.correr(c, ["2.1.4"], ejecutar=lambda cmd, salida: 1) == 0
    assert not (vieja / "workflow.json").exists()  # la carpeta evaluada es solo de esta corrida
    assert (c["corridas"] / "2.1.4.anterior" / "workflow.json").is_file()  # lo anterior se conserva aparte
    escenarios.comprobar_todos(c)
    r = json.loads((c["resultados"] / "escenarios.json").read_text())["escenarios"]["2.1.4"]
    assert r["corrida"]["codigo"] == 1 and r["veredicto_automatico"] == "no"
