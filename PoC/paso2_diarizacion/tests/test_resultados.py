"""Tareas 4.1 y 4.2: carpeta de la reunión, escritura del par y registro del error."""

import json

from contrato import validar_par
from resultados import (NOMBRE_ERROR, NOMBRE_JSON, NOMBRE_META, carpeta_reunion, escribir_par,
                        registrar_error)

SEGS = [{"start": 0.0, "end": 1.5, "speaker": "SPEAKER_00"}]


def _meta(run_id="r-anterior"):
    return {"run_id": run_id, "segmentos": 1, "hablantes": 1}


def _error(carpeta, run_id="r-nuevo"):
    return registrar_error(carpeta, run_id=run_id, inicio="2026-11-07T10:00:00-03:00", etapa="ejecucion",
                           tipo="RuntimeError", mensaje="fallo simulado", modo_dispositivo="auto")


def test_dos_grabaciones_de_la_misma_carpeta(tmp_path):
    a = carpeta_reunion(tmp_path / "2026_11_07_10_00_00.wav")
    b = carpeta_reunion(tmp_path / "2026_11_07_11_30_00.wav")
    assert a != b
    assert a == tmp_path / "2026_11_07_10_00_00"
    assert carpeta_reunion(tmp_path / "x.wav", tmp_path / "otra") == tmp_path / "otra"


def test_carpeta_no_pisa_el_reporte_del_paso_1(tmp_path):
    carpeta = carpeta_reunion(tmp_path / "2026_11_07_10_00_00.wav")
    assert carpeta != tmp_path / "2026_11_07_10_00_00.json"


def test_par_consistente_y_sin_tmp(tmp_path):
    meta = escribir_par(tmp_path, {"segments": SEGS}, _meta())
    assert validar_par(tmp_path / NOMBRE_JSON, tmp_path / NOMBRE_META) == []
    assert json.loads((tmp_path / NOMBRE_JSON).read_text(encoding="utf-8")) == {"segments": SEGS}
    assert len(meta["diarization_sha256"]) == 64
    assert not list(tmp_path.glob("*.tmp"))


def test_exito_borra_el_error_anterior(tmp_path):
    _error(tmp_path)
    assert (tmp_path / NOMBRE_ERROR).is_file()
    escribir_par(tmp_path, {"segments": SEGS}, _meta())
    assert not (tmp_path / NOMBRE_ERROR).exists()


def test_error_conserva_el_par_anterior_byte_a_byte(tmp_path):
    escribir_par(tmp_path, {"segments": SEGS}, _meta("r-anterior"))
    antes = {n: (tmp_path / n).read_bytes() for n in (NOMBRE_JSON, NOMBRE_META)}
    ruta = _error(tmp_path)
    assert {n: (tmp_path / n).read_bytes() for n in (NOMBRE_JSON, NOMBRE_META)} == antes
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["resultado_anterior_conservado"] is True
    assert datos["run_id_anterior"] == "r-anterior"
    assert datos["run_id"] == "r-nuevo" and datos["etapa"] == "ejecucion"
    assert set(datos) == {"run_id", "inicio", "etapa", "tipo", "mensaje", "modo_dispositivo",
                          "resultado_anterior_conservado", "run_id_anterior"}


def test_error_sin_par_previo_no_crea_resultado(tmp_path):
    carpeta = tmp_path / "reunion"
    ruta = _error(carpeta)
    assert ruta.is_file()
    assert not (carpeta / NOMBRE_JSON).exists() and not (carpeta / NOMBRE_META).exists()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["resultado_anterior_conservado"] is False and datos["run_id_anterior"] is None
    assert not list(carpeta.glob("*.tmp"))
