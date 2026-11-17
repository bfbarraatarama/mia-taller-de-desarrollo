"""Issue #15, grupo 2: comprobaciones automáticas de los escenarios (requisito «Comprobaciones automáticas»)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluacion.escenarios.comprobaciones import comprobar


def escribir(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos), encoding="utf-8")


def corrida(tmp_path: Path, *, estado="completado", fuentes=1, diar=None, trans=None, bloques=1, error=None) -> tuple[Path, list[str]]:
    """Carpeta como la que deja `src.pipeline ejecutar`, con `fuentes` archivos de entrada."""
    c = tmp_path / "corrida"
    shas, registro = [], []
    for i in range(1, fuentes + 1):
        datos = f"audio {i}".encode()
        (c / "fuentes").mkdir(parents=True, exist_ok=True)
        (c / "fuentes" / f"{i:03d}-audio.wav").write_bytes(datos)
        sha = hashlib.sha256(datos).hexdigest()
        shas.append(sha)
        registro.append({"orden": i, "fuente": f"fuentes/{i:03d}-audio.wav", "sha256_fuente": sha})
    escribir(c / "ingesta.json", {"fuentes": registro})
    escribir(c / "workflow.json", {"estado": estado, "error": error, "etapas": {}})
    if diar is not None:
        escribir(c / "diarization.json", {"segments": diar})
    if trans is not None:
        escribir(c / "transcription.json", {"segments": trans})
    if estado == "completado":
        escribir(c / "ejecucion_minutas.json", {"bloques_extraccion": bloques})
        escribir(c / "minutes.json", {"resumen": "x"})
    return c, shas


def seg(s, e, q):
    return {"start": s, "end": e, "speaker": q}


def interv(s, e, q, ambiguous=False, overlap=False):
    return {"start": s, "end": e, "speaker": q, "text": "x", "ambiguous": ambiguous, "overlap": overlap}


def por_nombre(reporte: dict) -> dict:
    return {c["comprobacion"]: c for c in reporte["comprobaciones"]}


def test_seis_o_mas_hablantes(tmp_path):
    diar = [seg(i, i + 2, f"SPEAKER_0{i}") for i in range(6)]
    trans = [interv(0, 1, "SPEAKER_00"), interv(1.5, 2.5, None, ambiguous=True), interv(3, 4, "SPEAKER_03", ambiguous=True)]
    carpeta, shas = corrida(tmp_path, diar=diar, trans=trans)
    reporte = comprobar("2.1.3", carpeta, shas)
    assert reporte["detalle"]["etiquetas_detectadas"] == 6
    assert reporte["detalle"]["intervenciones_ambiguas"] == 2
    c = por_nombre(reporte)
    assert c["Conserva el audio"]["resultado"] == "sí"
    assert c["Marca como ambiguas las intervenciones sin hablante"]["resultado"] == "sí"
    assert reporte["veredicto_automatico"] == "sí"


def test_intervencion_sin_hablante_no_marcada(tmp_path):
    carpeta, shas = corrida(tmp_path, diar=[seg(0, 2, "SPEAKER_00")], trans=[interv(0, 1, None, ambiguous=False)])
    reporte = comprobar("2.1.3", carpeta, shas)
    assert por_nombre(reporte)["Marca como ambiguas las intervenciones sin hablante"]["resultado"] == "no"
    assert reporte["veredicto_automatico"] == "no"


def test_minuta_por_fragmentos(tmp_path):
    carpeta, shas = corrida(tmp_path, fuentes=30, diar=[seg(0, 1, "A")], trans=[interv(0, 1, "A")], bloques=4)
    reporte = comprobar("2.1.5", carpeta, shas)
    assert reporte["detalle"]["bloques_extraccion"] == 4
    c = por_nombre(reporte)
    assert c["Procesa la minuta por fragmentos"]["resultado"] == "sí"
    assert c["Una sola transcripción para todos los archivos, en orden"]["resultado"] == "sí"


def test_un_solo_bloque_no_ejercita_el_escenario(tmp_path):
    carpeta, shas = corrida(tmp_path, fuentes=2, diar=[seg(0, 1, "A")], trans=[interv(0, 1, "A")], bloques=1)
    assert por_nombre(comprobar("2.1.5", carpeta, shas))["Procesa la minuta por fragmentos"]["resultado"] == "no"


def test_comprobacion_solo_visual(tmp_path):
    diar = [seg(0, 3, "SPEAKER_00"), seg(2, 4, "SPEAKER_01")]
    trans = [interv(0, 3, "SPEAKER_00", overlap=True, ambiguous=True)]
    carpeta, shas = corrida(tmp_path, diar=diar, trans=trans)
    reporte = comprobar("2.1.2", carpeta, shas)
    c = por_nombre(reporte)
    assert c["Conserva los solapamientos de la diarización"]["resultado"] == "sí"
    assert c["Mismo nombre en dos etiquetas: una sola persona"]["resultado"] == "manual"
    assert reporte["veredicto_automatico"] == "sí" and reporte["pendientes_manuales"] == 1


def test_etapa_que_falla_y_lo_informa(tmp_path):
    carpeta, shas = corrida(tmp_path, estado="error", error={"etapa": "minuta", "mensaje": "sin memoria"},
                            diar=[seg(0, 1, "A")], trans=[interv(0, 1, "A")])
    reporte = comprobar("2.1.4", carpeta, shas)
    c = por_nombre(reporte)
    assert c["Termina o informa la falla"]["resultado"] == "sí" and "minuta" in c["Termina o informa la falla"]["evidencia"]
    assert c["Conserva el audio"]["resultado"] == "sí"


def test_audio_alterado(tmp_path):
    carpeta, shas = corrida(tmp_path, diar=[seg(0, 1, "A")], trans=[interv(0, 1, "A")])
    (carpeta / "fuentes" / "001-audio.wav").write_bytes(b"otro")
    assert por_nombre(comprobar("2.1.4", carpeta, shas))["Conserva el audio"]["resultado"] == "no"


# ---------- revisión del #24 ----------

def test_superposicion_de_una_sola_etiqueta_no_cuenta(tmp_path):
    """Dos segmentos simultáneos del mismo hablante no son habla superpuesta (2.1.2 pide dos o más hablantes)."""
    diar = [seg(0, 3, "SPEAKER_00"), seg(1, 2, "SPEAKER_00")]
    carpeta, shas = corrida(tmp_path, diar=diar, trans=[interv(0, 3, "SPEAKER_00", ambiguous=True)])
    reporte = comprobar("2.1.2", carpeta, shas)
    assert reporte["detalle"]["segundos_superpuestos_diarizacion"] == 0
    assert por_nombre(reporte)["Conserva los solapamientos de la diarización"]["resultado"] == "no"


def test_superposicion_cuenta_etiquetas_distintas(tmp_path):
    diar = [seg(0, 3, "A"), seg(1, 2, "A"), seg(2.5, 4, "B")]  # A y B se pisan 0,5 s
    carpeta, shas = corrida(tmp_path, diar=diar, trans=[interv(0, 3, "A")])
    assert comprobar("2.1.2", carpeta, shas)["detalle"]["segundos_superpuestos_diarizacion"] == 0.5


def test_corrida_con_codigo_de_error_no_cuenta_como_completada(tmp_path):
    """Si la corrida terminó con error, un workflow «completado» no puede darla por buena."""
    carpeta, shas = corrida(tmp_path, diar=[seg(0, 1, "A")], trans=[interv(0, 1, "A")])
    reporte = comprobar("2.1.4", carpeta, shas, codigo=1)
    assert por_nombre(reporte)["Termina o informa la falla"]["resultado"] == "no"
    assert reporte["veredicto_automatico"] == "no"
