"""Tarea 6.4: planilla de minutas (requisito «Planilla de minutas», D10 y D17)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from evaluacion.modular.planilla import COLUMNAS, PlanillaInvalida, planillas_de_minutas

ITEMS = [{"tipo": "accion", "item_id": "R.a.1", "texto": "El diseñador industrial hará el prototipo.",
          "texto_original": "The industrial designer will make the prototype."},
         {"tipo": "decision", "item_id": "R.d.1", "texto": "Usarán botones grandes.",
          "texto_original": "They will use big buttons."},
         {"tipo": "resumen", "item_id": "R.s.1", "texto": "Se habló del presupuesto.",
          "texto_original": "The budget was discussed."}]


def armar(tmp_path: Path):
    datos, inferencia, planillas = tmp_path / "datos", tmp_path / "inf", tmp_path / "planillas"
    (datos / "ami/R").mkdir(parents=True)
    (datos / "ami/R/referencia_minuta.json").write_text(json.dumps({"sintetico": True, "items": ITEMS}), "utf-8")
    (inferencia / "ami-R").mkdir(parents=True)
    (inferencia / "ami-R/minutes.md").write_text("# Minuta\n\n- Prototipo a cargo del diseñador industrial.\n", "utf-8")
    elementos = [{"id": "ami-R", "fuente": "ami", "reunion": "R", "modulos": ["minutas"]},
                 {"id": "clip-x", "fuente": "openslr", "modulos": ["stt"]}]
    return elementos, datos, inferencia, planillas


def leer(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def marcar(ruta: Path, valores: list[str]) -> None:
    filas = leer(ruta)
    for fila, valor in zip(filas, valores):
        fila["recuperado"] = valor
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)


def test_planilla_sin_marcar(tmp_path):
    elementos, datos, inferencia, planillas = armar(tmp_path)
    reporte = planillas_de_minutas(elementos, datos, inferencia, planillas)
    filas = leer(planillas / "R.csv")
    assert [f["item_id"] for f in filas] == ["R.a.1", "R.d.1", "R.s.1"]
    assert all(f["recuperado"] == "" for f in filas)
    assert filas[0]["referencia"] == ITEMS[0]["texto"] and filas[0]["referencia_original"] == ITEMS[0]["texto_original"]
    assert (planillas / "R.minuta.md").read_text(encoding="utf-8").startswith("# Minuta")
    assert (planillas / "LEEME.md").is_file()
    assert reporte["reuniones"]["R"]["pendientes"] == 3 and reporte["total"]["marcados"] == 0


def test_planilla_marcada(tmp_path):
    elementos, datos, inferencia, planillas = armar(tmp_path)
    planillas_de_minutas(elementos, datos, inferencia, planillas)
    marcar(planillas / "R.csv", ["sí", "No", ""])
    antes = (planillas / "R.csv").read_bytes()
    reporte = planillas_de_minutas(elementos, datos, inferencia, planillas)
    assert (planillas / "R.csv").read_bytes() == antes  # no se modifica
    r = reporte["reuniones"]["R"]
    assert r["por_tipo"]["accion"] == {"items": 1, "marcados": 1, "recuperados": 1}
    assert r["por_tipo"]["decision"] == {"items": 1, "marcados": 1, "recuperados": 0}
    assert (r["marcados"], r["pendientes"]) == (2, 1)
    assert reporte["total"]["por_tipo"]["accion"]["recuperados"] == 1


def test_valor_invalido(tmp_path):
    elementos, datos, inferencia, planillas = armar(tmp_path)
    planillas_de_minutas(elementos, datos, inferencia, planillas)
    marcar(planillas / "R.csv", ["tal vez", "", ""])
    with pytest.raises(PlanillaInvalida, match="R.a.1"):
        planillas_de_minutas(elementos, datos, inferencia, planillas)


def test_minuta_cambiada_avisa_y_no_pisa(tmp_path):
    elementos, datos, inferencia, planillas = armar(tmp_path)
    planillas_de_minutas(elementos, datos, inferencia, planillas)
    (inferencia / "ami-R/minutes.md").write_text("# Otra minuta\n", "utf-8")
    reporte = planillas_de_minutas(elementos, datos, inferencia, planillas)
    assert (planillas / "R.minuta.md").read_text(encoding="utf-8").startswith("# Minuta")
    assert any("R" in a and "cambió" in a for a in reporte["avisos"])


def test_minuta_faltante(tmp_path):
    elementos, datos, inferencia, planillas = armar(tmp_path)
    (inferencia / "ami-R/minutes.md").unlink()
    reporte = planillas_de_minutas(elementos, datos, inferencia, planillas)
    assert reporte["faltantes"] == ["ami-R/minutes.md"] and not (planillas / "R.csv").exists()
