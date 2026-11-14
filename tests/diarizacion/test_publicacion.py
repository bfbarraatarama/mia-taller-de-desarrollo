"""Regresión de la integración de las rutas entre evaluación y publicación."""

import json

import pytest

from evaluacion.diarizacion import publicar_resultados as publicacion
from evaluacion.diarizacion import rutas
from . import test_evaluacion_calidad as calidad


@pytest.mark.parametrize("caso", ["valido", "ausente", "alterado"])
def test_publicacion_desde_reportes_de_evaluacion(tmp_path, monkeypatch, caso):
    assert calidad.REPORTES == publicacion.REPORTES == rutas.REPORTES
    assert calidad.DIRECTORIO == publicacion.DIRECTORIO == rutas.DIRECTORIO
    assert calidad.MANIFIESTO == rutas.MANIFIESTO
    # Construye una ejecución local compatible con las rutas actuales usando
    # las hipótesis publicadas reales. No recalcula ni cambia sus métricas.
    reportes, destino = tmp_path / "reportes", tmp_path / "resultados"
    reportes.mkdir()
    s = json.loads((rutas.RESULTADOS / "calidad_S26.json").read_text(encoding="utf-8"))
    s["parametros"]["manifiesto"]["ruta"] = rutas.MANIFIESTO.name
    esperados = {}
    for gid, g in s["grabaciones"].items():
        if g["estado"] != "valida":
            continue
        carpeta = reportes / "calidad" / gid / "principal"
        carpeta.mkdir(parents=True)
        hip = (rutas.RESULTADOS / "hipotesis_S26" / f"{gid}.json").read_bytes()
        (carpeta / "diarization.json").write_bytes(hip)
        g["principal"]["hipotesis"] = carpeta.relative_to(tmp_path).as_posix()
        esperados[f"hipotesis_S26/{gid}.json"] = hip
    assert len(esperados) == 25
    esperados["calidad_S26.json"] = json.dumps(s, ensure_ascii=False).encode("utf-8")
    esperados["calidad_total.json"] = (rutas.RESULTADOS / "calidad_total.json").read_bytes()
    for nombre in ("calidad_S26.json", "calidad_total.json"):
        (reportes / nombre).write_bytes(esperados[nombre])
    monkeypatch.setattr(publicacion, "DIRECTORIO", tmp_path)
    monkeypatch.setattr(publicacion, "REPORTES", reportes)
    monkeypatch.setattr(publicacion, "DESTINO", destino)
    hip = next(reportes.rglob("diarization.json"))
    if caso == "ausente":
        hip.unlink()
    elif caso == "alterado":
        hip.write_bytes(hip.read_bytes() + b"\n")
    if caso == "valido":
        assert publicacion.main([]) == 0
        assert {p.relative_to(destino).as_posix(): p.read_bytes()
                for p in destino.rglob("*.json")} == esperados
    else:
        assert publicacion.main([]) == 1
        assert not destino.exists()
