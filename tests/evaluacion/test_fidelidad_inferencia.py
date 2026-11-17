import csv
from types import SimpleNamespace

import pytest

from evaluacion.fidelidad_minutas.archivos import REUNIONES_EJEMPLO, guardar_json, leer_json, sha256
from evaluacion.fidelidad_minutas.evaluacion import juzgar, reportar
from evaluacion.fidelidad_minutas.inferencia import inferir
from src.minutas.proveedores import RespuestaModelo


class Cliente:
    nombre = "simulado"
    proveedor = "ollama"

    def responder(self, instrucciones, datos, esquema):
        return RespuestaModelo({"resumen": "Resumen sintético.", "decisiones": [], "problemas": [], "acciones": []})


class Juez:
    identidad = {"digest": "juez"}
    prompt_sha = "prompt"

    def evaluar(self, referencia, minuta, ejemplo):
        ejemplo.verificar()
        return SimpleNamespace(resultado="sí", citas=[], observaciones=""), ""


def test_flujo_con_datos_y_modelos_simulados(tmp_path):
    carpeta = tmp_path / "run"
    muestra = carpeta / "muestra"
    registros = []
    for reunion in ("A", "B", "C"):
        destino = muestra / "ami" / reunion
        destino.mkdir(parents=True)
        entrada = {"segments": [
            {"start": i * 2, "end": i * 2 + 1, "speaker": "A", "name": None,
             "text": f"Texto número {i} sobre la reunión.", "overlap": False, "ambiguous": False}
            for i in range(4)]}
        guardar_json(destino / "transcription.json", entrada)
        guardar_json(destino / "referencia_minuta.json", {"items": [
            {"tipo": "resumen", "item_id": f"{reunion}.1", "texto": "La reunión.",
             "texto_original": "The meeting."}]})
        guardar_json(destino / "traduccion.json", {"sintetico": True})
        registros.append({"reunion": reunion, "archivos": {
            n: sha256(destino / n) for n in ("transcription.json", "referencia_minuta.json", "traduccion.json")}})
    guardar_json(muestra / "manifiesto.json", {"reuniones": registros})
    planillas = tmp_path / "planillas"
    planillas.mkdir()
    for reunion in REUNIONES_EJEMPLO:
        (planillas / f"{reunion}.minuta.md").write_text("Ejemplo", encoding="utf-8")
        with (planillas / f"{reunion}.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=("reunion", "tipo", "item_id", "referencia", "recuperado"))
            w.writeheader()
            w.writerow({"reunion": reunion, "tipo": "resumen", "item_id": reunion, "referencia": "Ejemplo",
                        "recuperado": "sí"})
    inferir(carpeta, cliente=Cliente(), identidad={"digest": "generador"})
    juzgar(carpeta, planillas, juez=Juez())
    reportar(carpeta)
    reporte = leer_json(carpeta / "reporte.json")
    assert set(reporte["reuniones"]) == {"A", "B", "C"}
    assert reporte["reuniones"]["A"]["total"]["delta_puntos_porcentuales"] == 0
    assert (carpeta / "reporte.md").exists()


def test_no_admite_destino_ollama_remoto(monkeypatch):
    from evaluacion.fidelidad_minutas.inferencia import modelo_local
    monkeypatch.setenv("OLLAMA_HOST", "https://modelo.example")
    with pytest.raises(ValueError, match="Ollama local"):
        modelo_local("qwen2.5:7b")
