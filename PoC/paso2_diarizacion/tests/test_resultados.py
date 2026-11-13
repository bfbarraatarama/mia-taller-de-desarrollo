"""Tareas 4.1, 4.2 y 4.6: carpeta de la reunión, escritura del par, publicación con reversión y error."""

import json
import os

import pytest

import resultados
from contrato import validar_par
from resultados import (NOMBRE_ERROR, NOMBRE_JSON, NOMBRE_META, carpeta_reunion, escribir_par, par_vigente,
                        registrar_error, run_id_vigente)

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


# --- tarea 4.6: publicación con respaldo y reversión -------------------------------------------------------

SEGS_NUEVOS = [{"start": 0.0, "end": 2.0, "speaker": "SPEAKER_01"}]


def replace_que_falla(monkeypatch, falla_en: set[int]) -> list[tuple[str, str]]:
    """Reemplaza os.replace: las llamadas número `falla_en` (desde 1) lanzan OSError; el resto funciona."""
    real, llamadas = os.replace, []

    def falso(origen, destino):
        llamadas.append((os.path.basename(origen), os.path.basename(destino)))
        if len(llamadas) in falla_en:
            raise OSError(f"fallo simulado en os.replace #{len(llamadas)}")
        return real(origen, destino)

    monkeypatch.setattr(resultados.os, "replace", falso)
    return llamadas


def _par(carpeta):
    return {n: (carpeta / n).read_bytes() for n in (NOMBRE_JSON, NOMBRE_META)}


def _sin_restos(carpeta):
    return not list(carpeta.glob("*.tmp")) and not list(carpeta.glob("*.bak"))


def test_falla_la_segunda_publicacion_con_par_anterior(tmp_path, monkeypatch):
    escribir_par(tmp_path, {"segments": SEGS}, _meta("r-anterior"))
    antes = _par(tmp_path)
    llamadas = replace_que_falla(monkeypatch, {2})
    with pytest.raises(OSError, match="#2"):
        escribir_par(tmp_path, {"segments": SEGS_NUEVOS}, _meta("r-nuevo"))
    assert _par(tmp_path) == antes
    assert validar_par(tmp_path / NOMBRE_JSON, tmp_path / NOMBRE_META) == []
    assert run_id_vigente(tmp_path) == "r-anterior"
    assert _sin_restos(tmp_path)
    # 1: publica el JSON; 2: falla el meta; 3: restaura el JSON desde su respaldo
    assert [d for _, d in llamadas] == [NOMBRE_JSON, NOMBRE_META, NOMBRE_JSON]
    assert llamadas[2][0].startswith(NOMBRE_JSON + ".") and llamadas[2][0].endswith(".bak")


def test_falla_la_segunda_publicacion_sin_par_anterior(tmp_path, monkeypatch):
    carpeta = tmp_path / "reunion"
    replace_que_falla(monkeypatch, {2})
    with pytest.raises(OSError, match="#2"):
        escribir_par(carpeta, {"segments": SEGS_NUEVOS}, _meta("r-nuevo"))
    assert not (carpeta / NOMBRE_JSON).exists() and not (carpeta / NOMBRE_META).exists()
    assert _sin_restos(carpeta) and run_id_vigente(carpeta) is None


def test_falla_la_primera_publicacion(tmp_path, monkeypatch):
    escribir_par(tmp_path, {"segments": SEGS}, _meta("r-anterior"))
    antes = _par(tmp_path)
    llamadas = replace_que_falla(monkeypatch, {1})
    with pytest.raises(OSError, match="#1"):
        escribir_par(tmp_path, {"segments": SEGS_NUEVOS}, _meta("r-nuevo"))
    assert _par(tmp_path) == antes and _sin_restos(tmp_path)
    assert len(llamadas) == 1  # nada publicado, nada que restaurar


def test_falla_la_restauracion_y_se_conservan_los_respaldos(tmp_path, monkeypatch):
    escribir_par(tmp_path, {"segments": SEGS}, _meta("r-anterior"))
    antes = _par(tmp_path)
    replace_que_falla(monkeypatch, {2, 3})  # falla el meta y también la restauración del JSON
    with pytest.raises(OSError, match="#2") as e:
        escribir_par(tmp_path, {"segments": SEGS_NUEVOS}, _meta("r-nuevo"))
    assert any("No se pudo restaurar diarization.json" in nota for nota in e.value.__notes__)
    # el par quedó inconsistente (JSON nuevo, meta anterior), pero se detecta
    assert run_id_vigente(tmp_path) is None and par_vigente(tmp_path) is None
    assert validar_par(tmp_path / NOMBRE_JSON, tmp_path / NOMBRE_META)
    # los respaldos quedan y alcanzan para recuperar el par anterior byte a byte
    respaldo_json, = tmp_path.glob(f"{NOMBRE_JSON}.*.bak")
    respaldo_meta, = tmp_path.glob(f"{NOMBRE_META}.*.bak")
    assert {NOMBRE_JSON: respaldo_json.read_bytes(), NOMBRE_META: respaldo_meta.read_bytes()} == antes
    assert not list(tmp_path.glob("*.tmp"))


def test_una_reversion_fallida_no_pisa_sus_respaldos(tmp_path, monkeypatch):
    escribir_par(tmp_path, {"segments": SEGS}, _meta("r-anterior"))
    replace_que_falla(monkeypatch, {2, 3})
    with pytest.raises(OSError):
        escribir_par(tmp_path, {"segments": SEGS_NUEVOS}, _meta("r-nuevo"))
    respaldos = {p.name: p.read_bytes() for p in tmp_path.glob("*.bak")}
    monkeypatch.undo()
    escribir_par(tmp_path, {"segments": SEGS}, _meta("r-otra"))  # una ejecución posterior que sale bien
    assert {p.name: p.read_bytes() for p in tmp_path.glob("*.bak")} == respaldos
    assert run_id_vigente(tmp_path) == "r-otra"


def test_falla_al_preparar_el_respaldo(tmp_path, monkeypatch):
    escribir_par(tmp_path, {"segments": SEGS}, _meta("r-anterior"))
    antes = _par(tmp_path)

    def sin_espacio(destino, marca):
        raise OSError("disco lleno (simulado)")

    monkeypatch.setattr(resultados, "_respaldar", sin_espacio)
    with pytest.raises(OSError, match="disco lleno"):
        escribir_par(tmp_path, {"segments": SEGS_NUEVOS}, _meta("r-nuevo"))
    assert _par(tmp_path) == antes and _sin_restos(tmp_path)


def test_par_inconsistente_no_cuenta_como_vigente(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    escribir_par(a, {"segments": SEGS}, _meta("r-a"))
    escribir_par(b, {"segments": SEGS_NUEVOS}, _meta("r-b"))
    (a / NOMBRE_META).write_bytes((b / NOMBRE_META).read_bytes())  # JSON de r-a con el meta de r-b
    assert par_vigente(a) is None and run_id_vigente(a) is None
    datos = json.loads(_error(a).read_text(encoding="utf-8"))
    assert datos["resultado_anterior_conservado"] is False and datos["run_id_anterior"] is None
    assert par_vigente(b)["run_id"] == "r-b"


def test_meta_que_no_es_un_objeto_no_cuenta_como_vigente(tmp_path):
    escribir_par(tmp_path, {"segments": SEGS}, _meta())
    (tmp_path / NOMBRE_META).write_text("[1, 2]", encoding="utf-8")
    assert run_id_vigente(tmp_path) is None


def test_exito_no_deja_respaldos(tmp_path):
    escribir_par(tmp_path, {"segments": SEGS}, _meta("r-anterior"))
    escribir_par(tmp_path, {"segments": SEGS_NUEVOS}, _meta("r-nuevo"))
    assert _sin_restos(tmp_path) and run_id_vigente(tmp_path) == "r-nuevo"
    assert json.loads((tmp_path / NOMBRE_JSON).read_text(encoding="utf-8")) == {"segments": SEGS_NUEVOS}


def test_error_sin_par_previo_no_crea_resultado(tmp_path):
    carpeta = tmp_path / "reunion"
    ruta = _error(carpeta)
    assert ruta.is_file()
    assert not (carpeta / NOMBRE_JSON).exists() and not (carpeta / NOMBRE_META).exists()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["resultado_anterior_conservado"] is False and datos["run_id_anterior"] is None
    assert not list(carpeta.glob("*.tmp"))
