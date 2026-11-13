"""Grupo 5: modelo de las fichas, sin Qt (D8). Orden, nombres, ayudas, cierre y speakers.json."""

from __future__ import annotations

import pytest

from asociacion import asociar
from conftest import crear_reunion, leer, segmento, sha256
from contrato import validar_speakers
from etiquetado import CIERRE_POR_DEFECTO, Cierre, ModeloFichas, aplicar, normalizar
from fragmentos import fragmentos
from test_salida import _lector_etapa5

ENTRADAS = ("audio.wav", "diarization.json", "asr.json")


@pytest.fixture
def tres(tmp_path):
    """SPEAKER_00 habla 30 s en 5 tramos solos de 6 s (5 candidatos); SPEAKER_01 5 s; SPEAKER_02 3 s."""
    turnos = [(0, 6, "SPEAKER_00"), (6, 7, "SPEAKER_01"), (7, 8, "SPEAKER_02"), (8, 14, "SPEAKER_00"),
              (14, 15, "SPEAKER_01"), (15, 16, "SPEAKER_02"), (16, 22, "SPEAKER_00"), (22, 23, "SPEAKER_01"),
              (23, 24, "SPEAKER_02"), (24, 30, "SPEAKER_00"), (32, 38, "SPEAKER_00"), (38, 40, "SPEAKER_01")]
    segmentos = [segmento(("Hola", 1.0, 2.0)), segmento(("Sí.", 6.2, 6.8)), segmento(("Dale.", 7.2, 7.8))]
    return crear_reunion(tmp_path / "reunion", 40.0, [(float(a), float(b), e) for a, b, e in turnos], segmentos)


def nombres_en(carpeta):
    """{speaker: name} de transcription.json y {etiqueta: name} de speakers.json."""
    transcripcion = {s["speaker"]: s["name"] for s in leer(carpeta / "transcription.json")["segments"]}
    speakers = {e: v["name"] for e, v in leer(carpeta / "speakers.json").items()}
    return transcripcion, speakers


# ---------- 5.1 orden ----------


def test_orden_por_tiempo_de_habla(tmp_path):
    carpeta = crear_reunion(tmp_path, 10.0, [(0.0, 3.0, "SPEAKER_00"), (3.0, 9.0, "SPEAKER_01")],
                            [segmento(("hola", 0.5, 1.0))])
    m = ModeloFichas(asociar(carpeta))
    assert [(f.etiqueta, f.tiempo_habla_s) for f in m.fichas] == [("SPEAKER_01", 6.0), ("SPEAKER_00", 3.0)]


def test_mismo_tiempo_de_habla_por_etiqueta(tmp_path):
    carpeta = crear_reunion(tmp_path, 10.0, [(0.0, 3.0, "SPEAKER_01"), (3.0, 6.0, "SPEAKER_00")],
                            [segmento(("hola", 0.5, 1.0))])
    assert [f.etiqueta for f in ModeloFichas(asociar(carpeta)).fichas] == ["SPEAKER_00", "SPEAKER_01"]


def test_diarizacion_vacia_sin_fichas(tmp_path):
    carpeta = crear_reunion(tmp_path, 5.0, [], [segmento(("hola", 0.5, 1.0))])
    m = ModeloFichas(asociar(carpeta))
    assert m.fichas == [] and not m.hay_fichas


# ---------- 5.2 nombres ----------


@pytest.mark.parametrize("escrito, esperado", [
    ("  Luisa  ", "Luisa"), ("Ana   María", "Ana María"), ("\tBruno\n", "Bruno"), ("", None), ("   ", None),
])
def test_normalizar(escrito, esperado):
    assert normalizar(escrito) == esperado


def test_misma_persona_en_dos_etiquetas(tres):
    a = asociar(tres)
    m = ModeloFichas(a)
    m.escribir_nombre("SPEAKER_00", "Luisa")
    m.escribir_nombre("SPEAKER_01", "Bruno")
    m.escribir_nombre("SPEAKER_02", "luisa ")
    aplicar(a, m.confirmar())
    transcripcion, speakers = nombres_en(tres)
    esperado = {"SPEAKER_00": "Luisa", "SPEAKER_01": "Bruno", "SPEAKER_02": "Luisa"}
    assert transcripcion == esperado and speakers == esperado


def test_primera_forma_en_el_orden_de_las_fichas(tmp_path):
    """SPEAKER_01 habla más, así que su ficha va primero y su forma («ana») es la que queda."""
    carpeta = crear_reunion(tmp_path, 10.0, [(0.0, 3.0, "SPEAKER_00"), (3.0, 9.0, "SPEAKER_01")],
                            [segmento(("hola", 0.5, 1.0))])
    m = ModeloFichas(asociar(carpeta))
    m.escribir_nombre("SPEAKER_00", "Ana")
    m.escribir_nombre("SPEAKER_01", "ana")
    assert m.confirmar().etiquetado.nombres == {"SPEAKER_00": "ana", "SPEAKER_01": "ana"}


def test_nombres_que_difieren_solo_en_tildes(tres):
    a = asociar(tres)
    m = ModeloFichas(a)
    m.escribir_nombre("SPEAKER_00", "Martín")
    m.escribir_nombre("SPEAKER_01", "Martin")
    assert m.avisos_tildes() == [("Martín", "Martin")]
    aplicar(a, m.confirmar())  # el usuario confirma igual
    _, speakers = nombres_en(tres)
    assert speakers["SPEAKER_00"] == "Martín" and speakers["SPEAKER_01"] == "Martin"


def test_sin_aviso_de_tildes_si_ya_se_unifican(tres):
    m = ModeloFichas(asociar(tres))
    m.escribir_nombre("SPEAKER_00", "MARTÍN")
    m.escribir_nombre("SPEAKER_01", "martín")
    assert m.avisos_tildes() == []


def test_nombre_vacio(tres):
    a = asociar(tres)
    m = ModeloFichas(a)
    m.escribir_nombre("SPEAKER_00", "Luisa")
    m.escribir_nombre("SPEAKER_01", "   ")  # SPEAKER_02 queda sin tocar
    aplicar(a, m.confirmar())
    transcripcion, speakers = nombres_en(tres)
    assert speakers == {"SPEAKER_00": "Luisa", "SPEAKER_01": None, "SPEAKER_02": None}
    assert transcripcion == speakers


# ---------- 5.3 ayudas ----------


def test_autocompletado(tres):
    m = ModeloFichas(asociar(tres))
    m.escribir_nombre("SPEAKER_00", "Luisa")
    assert m.sugerencias("SPEAKER_01", "Lu") == ["Luisa"]
    assert m.sugerencias("SPEAKER_01", "lu") == ["Luisa"]
    assert m.sugerencias("SPEAKER_00", "Lu") == []  # no se sugiere el nombre de la propia ficha
    m.escribir_nombre("SPEAKER_02", "luisa")
    assert m.sugerencias("SPEAKER_01") == ["Luisa"]  # una sola vez, con la primera forma


def test_contador_de_fragmentos(tres):
    m = ModeloFichas(asociar(tres))
    assert m.ficha("SPEAKER_00").contador == "fragmento 1 de 5"
    m.otro_fragmento("SPEAKER_00")
    assert m.ficha("SPEAKER_00").contador == "fragmento 2 de 5"
    for _ in range(4):
        m.otro_fragmento("SPEAKER_00")
    assert m.ficha("SPEAKER_00").contador == "fragmento 1 de 5"


def test_aviso_de_superposicion(tmp_path):
    carpeta = crear_reunion(tmp_path, 25.0, [(0.0, 20.0, "SPEAKER_00"), (6.0, 9.0, "SPEAKER_01")],
                            [segmento(("hola", 0.5, 1.0))])
    m = ModeloFichas(asociar(carpeta))
    assert m.ficha("SPEAKER_01").aviso_superposicion and not m.ficha("SPEAKER_00").aviso_superposicion


# ---------- 5.4 cierre y speakers.json ----------


def test_fragmento_en_pantalla_al_confirmar(tres):
    a = asociar(tres)
    m = ModeloFichas(a)
    m.otro_fragmento("SPEAKER_00")
    m.otro_fragmento("SPEAKER_00")
    aplicar(a, m.confirmar())
    tercero = fragmentos(a)["SPEAKER_00"].en(2)
    clip = leer(tres / "speakers.json")["SPEAKER_00"]
    assert (clip["clip_start"], clip["clip_end"]) == (tercero.start, tercero.end)
    assert m.ficha("SPEAKER_00").fragmento == tercero


def test_volver_a_las_fichas(tres):
    m = ModeloFichas(asociar(tres))
    m.escribir_nombre("SPEAKER_00", "Luisa")
    assert CIERRE_POR_DEFECTO is Cierre.VOLVER
    assert m.cerrar_sin_confirmar(CIERRE_POR_DEFECTO).accion == "volver"
    assert m.ficha("SPEAKER_00").nombre == "Luisa"
    assert not (tres / "transcription.json").exists()


def test_seguir_sin_nombres(tres):
    a = asociar(tres)
    m = ModeloFichas(a)
    m.escribir_nombre("SPEAKER_00", "Luisa")
    decision = m.cerrar_sin_confirmar(Cierre.SIN_NOMBRES)
    assert decision.accion == "escribir" and decision.etiquetado is None
    assert aplicar(a, decision) == tres / "transcription.json"
    assert all(s["name"] is None for s in leer(tres / "transcription.json")["segments"])
    assert not (tres / "speakers.json").exists()
    assert leer(tres / "transcription.meta.json")["etiquetado"] is False


def test_seguir_sin_nombres_despues_de_etiquetar(tres):
    """Un speakers.json de un etiquetado anterior no debe quedar contradiciendo a transcription.json."""
    a = asociar(tres)
    m = ModeloFichas(a)
    m.escribir_nombre("SPEAKER_00", "Luisa")
    aplicar(a, m.confirmar())
    aplicar(a, ModeloFichas(a).cerrar_sin_confirmar(Cierre.SIN_NOMBRES))
    assert not (tres / "speakers.json").exists()


def test_cancelar(tres):
    antes = {n: sha256(tres / n) for n in ENTRADAS}
    a = asociar(tres)
    decision = ModeloFichas(a).cerrar_sin_confirmar(Cierre.CANCELAR)
    assert decision.accion == "cancelar" and aplicar(a, decision) is None
    assert not (tres / "transcription.json").exists() and not (tres / "speakers.json").exists()
    assert {n: sha256(tres / n) for n in ENTRADAS} == antes


def test_cancelar_con_resultado_anterior(tres):
    a = asociar(tres)
    m = ModeloFichas(a)
    m.escribir_nombre("SPEAKER_00", "Luisa")
    aplicar(a, m.confirmar())
    salidas = ("transcription.json", "transcription.meta.json", "speakers.json")
    antes = {n: sha256(tres / n) for n in salidas}
    aplicar(a, ModeloFichas(a).cerrar_sin_confirmar(Cierre.CANCELAR))
    assert {n: sha256(tres / n) for n in salidas} == antes


def test_metadatos_con_etiquetado(tres):
    a = asociar(tres)
    aplicar(a, ModeloFichas(a).confirmar())
    meta = leer(tres / "transcription.meta.json")
    assert meta["etiquetado"] is True and meta["sha256"]["speakers.json"] == sha256(tres / "speakers.json")


def test_speakers_json_dentro_del_contrato(tres):
    a = asociar(tres)
    m = ModeloFichas(a)
    m.escribir_nombre("SPEAKER_01", "Bruno")
    aplicar(a, m.confirmar())
    assert validar_speakers(leer(tres / "speakers.json"), a.duracion, a.etiquetas) == []


@pytest.mark.parametrize("cambio, regla", [
    (lambda d: d.pop("SPEAKER_01"), "falta"),
    (lambda d: d.update(SPEAKER_09={"name": None, "clip_start": 0.0, "clip_end": 1.0}), "no está"),
    (lambda d: d["SPEAKER_00"].update(extra=1), "campo"),
    (lambda d: d["SPEAKER_00"].update(name=""), "name"),
    (lambda d: d["SPEAKER_00"].update(clip_end=11.0), "duración"),
    (lambda d: d["SPEAKER_00"].update(clip_start=2.0), "clip_start < clip_end"),
    (lambda d: d["SPEAKER_00"].update(clip_start=0.1234), "decimales"),
])
def test_speakers_invalido(cambio, regla):
    datos = {"SPEAKER_00": {"name": "Luisa", "clip_start": 0.0, "clip_end": 2.0},
             "SPEAKER_01": {"name": None, "clip_start": 3.0, "clip_end": 5.0}}
    cambio(datos)
    violaciones = validar_speakers(datos, 10.0, ("SPEAKER_00", "SPEAKER_01"))
    assert violaciones and regla in " ".join(violaciones)


def test_lectura_por_la_etapa_5_con_nombres(tres):
    entrada = _lector_etapa5()
    a = asociar(tres)
    m = ModeloFichas(a)
    m.escribir_nombre("SPEAKER_00", "Luisa")
    aplicar(a, m.confirmar())
    intervenciones, _ = entrada.leer_transcripcion(tres / "transcription.json")
    assert [(i.hablante, i.nombre) for i in intervenciones][:2] == [("SPEAKER_00", "Luisa"), ("SPEAKER_01", None)]
