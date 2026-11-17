import csv
from types import SimpleNamespace

import pytest

from evaluacion.fidelidad_minutas.archivos import REUNIONES_EJEMPLO, leer_csv, leer_json
from evaluacion.fidelidad_minutas.evaluar_juez import evaluar
from evaluacion.fidelidad_minutas.juez import agregar, validar_respuesta


class JuezFalso:
    identidad = {"digest": "modelo-de-prueba"}
    prompt_sha = "prompt-de-prueba"

    def evaluar(self, referencia, minuta, ejemplo):
        assert referencia and minuta and ejemplo.items
        ejemplo.verificar()
        return SimpleNamespace(resultado="sí", citas=["cita inventada"], observaciones=""), ""


def test_votos_y_citas_no_verificadas():
    assert agregar(["sí", "no"]) == "incierto"
    assert agregar(["sí", "no", "no_evaluable"]) == "incierto"
    assert agregar(["sí", "sí", "no"]) == "sí"
    respuesta, aviso = validar_respuesta({"resultado": "sí", "observaciones": "", "citas": 42})
    assert respuesta.resultado == "sí" and respuesta.citas == [] and aviso
    with pytest.raises(ValueError, match="Votos"):
        agregar(["otro"])


def test_juez_independiente_dos_votos_por_item(tmp_path):
    planillas = tmp_path / "planillas"
    planillas.mkdir()
    for reunion in REUNIONES_EJEMPLO:
        (planillas / f"{reunion}.minuta.md").write_text("Minuta de ejemplo.", encoding="utf-8")
        with (planillas / f"{reunion}.csv").open("w", encoding="utf-8", newline="") as archivo:
            w = csv.DictWriter(archivo, fieldnames=("reunion", "tipo", "item_id", "referencia", "recuperado"))
            w.writeheader()
            for i, marca in enumerate(("sí", "no", "") if reunion == "TS3009a" else ("sí", "no")):
                w.writerow({"reunion": reunion, "tipo": "accion", "item_id": f"{reunion}-{i}",
                            "referencia": "Referencia de ejemplo.", "recuperado": marca})
    destino = tmp_path / "juez"
    evaluar(planillas, destino, juez=JuezFalso())
    votos = leer_csv(destino / "predicciones.csv")
    filas = leer_csv(destino / "agregados.csv")
    assert len(votos) == 14 and len(filas) == 7
    assert all(v["reunion"] != v["ejemplo_reunion"] for v in votos)
    reporte = leer_json(destino / "reporte.json")
    assert reporte["global"]["sin_marca_humana"] == 1
    assert reporte["global"]["exactitud"]["denominador"] == 6
